from app.integrations.opensearch_store import OpenSearchSparseStore
from app.rag.retriever import (
    HybridRetriever,
    ParentChildExpander,
    RerankPipeline,
    RetrievalHit,
    clean_rerank_passage,
    tokenize_query,
)
from app.schemas.quick_answer import SourceRead


class FakeKeywordRetriever:
    def __init__(self, hits):
        self.hits = hits

    def search(self, query: str, *, knowledge_base_id: str, limit: int, score_threshold: float | None = None):
        return self.hits[:limit]


class FakeVectorRetriever(FakeKeywordRetriever):
    pass


class FakeReranker:
    def rerank(self, *, query: str, documents: list[str], top_n: int):
        return [(1, 0.91), (0, 0.42)][:top_n]


class FixedScoreReranker:
    def __init__(self, scores):
        self.scores = scores
        self.calls = 0

    def rerank(self, *, query: str, documents: list[str], top_n: int):
        self.calls += 1
        return self.scores[:top_n]


class FakeChunkRepo:
    def get(self, chunk_id: str):
        if chunk_id == "parent-1":
            return type(
                "ChunkRow",
                (),
                {
                    "id": "parent-1",
                    "content": "父块上下文",
                    "context_header": "## 父标题",
                },
            )()
        return None


def test_hybrid_retriever_merges_vector_and_keyword_hits_with_weighted_rrf():
    vector_hit = RetrievalHit(
        chunk_id="shared",
        document_id="doc-1",
        knowledge_base_id="kb-1",
        content="shared vector",
        score=0.9,
        vector_score=0.9,
        retrieval_method="vector",
    )
    keyword_hit = RetrievalHit(
        chunk_id="keyword-only",
        document_id="doc-2",
        knowledge_base_id="kb-1",
        content="keyword only",
        score=0.7,
        keyword_score=0.7,
        retrieval_method="keyword",
    )

    result = HybridRetriever(
        vector_retriever=FakeVectorRetriever([vector_hit]),
        keyword_retriever=FakeKeywordRetriever([keyword_hit, vector_hit]),
        rrf_k=60,
        vector_weight=0.7,
        keyword_weight=0.3,
    ).search("问题", knowledge_base_id="kb-1", limit=10)

    assert [hit.chunk_id for hit in result] == ["shared", "keyword-only"]
    assert result[0].retrieval_method == "hybrid"
    assert result[0].vector_score == 0.9
    assert result[0].keyword_score == 0.9
    assert round(result[0].rrf_score, 6) == round(0.7 / 61 + 0.3 / 62, 6)


def test_rerank_pipeline_cleans_passages_filters_and_maps_scores():
    hits = [
        RetrievalHit(
            chunk_id="first",
            document_id="doc-1",
            knowledge_base_id="kb-1",
            content="```python\nprint('x')\n```\n有效内容",
            score=0.2,
        ),
        RetrievalHit(
            chunk_id="second",
            document_id="doc-2",
            knowledge_base_id="kb-1",
            content="| a | b |\n| - | - |\n| c | d |\n更相关内容",
            score=0.3,
        ),
    ]

    result = RerankPipeline(FakeReranker(), threshold=0.5, top_k=2).apply("问题", hits)

    assert [hit.chunk_id for hit in result] == ["second"]
    assert result[0].rerank_score == 0.91
    assert "```" not in clean_rerank_passage(hits[0].content)
    assert "|" not in clean_rerank_passage(hits[1].content)


def test_rerank_pipeline_degrades_high_threshold_before_returning_empty_results():
    reranker = FixedScoreReranker([(0, 0.6), (1, 0.4)])
    hits = [
        RetrievalHit("first", "doc-1", "kb-1", "相关内容 A", 0.2),
        RetrievalHit("second", "doc-2", "kb-1", "相关内容 B", 0.1),
    ]

    pipeline = RerankPipeline(reranker, threshold=0.8, top_k=2)
    result = pipeline.apply("问题", hits)

    assert [hit.chunk_id for hit in result] == ["first"]
    assert reranker.calls == 2
    assert pipeline.diagnostics["original_threshold"] == 0.8
    assert pipeline.diagnostics["degraded_threshold"] == 0.56


def test_rerank_pipeline_applies_mmr_to_reduce_redundant_chunks():
    reranker = FixedScoreReranker([(0, 0.95), (1, 0.94), (2, 0.7)])
    hits = [
        RetrievalHit("first", "doc-1", "kb-1", "重复 内容 关键能力 平台 检索", 0.9),
        RetrievalHit("duplicate", "doc-2", "kb-1", "重复 内容 关键能力 平台 检索", 0.88),
        RetrievalHit("different", "doc-3", "kb-1", "完全不同 主题 运维 状态 追踪", 0.7),
    ]

    pipeline = RerankPipeline(reranker, threshold=0.2, top_k=2)
    result = pipeline.apply("问题", hits)

    assert [hit.chunk_id for hit in result] == ["first", "different"]
    assert pipeline.diagnostics["mmr_input_count"] == 3
    assert pipeline.diagnostics["mmr_output_count"] == 2


def test_clean_rerank_passage_removes_markdown_links_tables_code_and_raw_urls():
    content = """
    # 标题
    [产品文档](https://example.com/docs) 说明关键能力。
    https://example.com/raw
    ```python
    print("noise")
    ```
    | a | b |
    | - | - |
    | c | d |
    """

    cleaned = clean_rerank_passage(content)

    assert "产品文档" in cleaned
    assert "https://example.com" not in cleaned
    assert "```" not in cleaned
    assert "|" not in cleaned
    assert "print" not in cleaned


def test_parent_child_expander_uses_parent_context_but_keeps_matched_child_identity():
    hit = RetrievalHit(
        chunk_id="child-1",
        document_id="doc-1",
        knowledge_base_id="kb-1",
        content="子块内容",
        score=0.8,
        parent_chunk_id="parent-1",
        chunk_type="child",
    )

    result = ParentChildExpander(FakeChunkRepo()).expand([hit])

    assert result[0].chunk_id == "child-1"
    assert result[0].content == "子块内容"
    assert result[0].context_content == "父块上下文"
    assert result[0].context_header == "## 父标题"
    assert result[0].context_chunk_id == "parent-1"

    serialized = SourceRead(
        document_id=result[0].document_id,
        knowledge_base_id=result[0].knowledge_base_id,
        chunk_id=result[0].chunk_id,
        content=result[0].content,
        score=result[0].score,
        context_content=result[0].context_content,
    ).model_dump()
    assert serialized["context_content"] == "父块上下文"


def test_tokenize_query_handles_chinese_terms_and_cjk_characters():
    terms = tokenize_query("知识库检索")

    assert "知" in terms
    assert "识" in terms
    assert "检" in terms
    assert "索" in terms
    assert any(term in terms for term in ("知识库", "知识", "检索"))


def test_tokenize_query_handles_english_terms():
    terms = tokenize_query("knowledge base retrieval")

    assert "knowledge" in terms
    assert "base" in terms
    assert "retrieval" in terms


def test_tokenize_query_handles_mixed_english_and_chinese_terms():
    terms = tokenize_query("RAG检索策略")

    assert "rag" in terms
    assert "检" in terms
    assert "索" in terms
    assert "策" in terms
    assert "略" in terms


def test_tokenize_query_filters_short_non_cjk_terms_but_keeps_single_cjk():
    assert "a" not in tokenize_query("a")
    assert tokenize_query("知") == ["知"]


def test_tokenize_query_returns_empty_list_for_empty_query():
    assert tokenize_query("") == []


def test_fake_vector_store_applies_score_threshold(fake_vector_store):
    fake_vector_store.results = [
        {"chunk_id": "low", "knowledge_base_id": "kb-1", "score": 0.2},
        {"chunk_id": "high", "knowledge_base_id": "kb-1", "score": 0.8},
    ]

    hits = fake_vector_store.search(
        knowledge_base_id="kb-1",
        query_vector=[0.0, 0.0, 0.0],
        limit=10,
        score_threshold=0.5,
    )

    assert [hit["chunk_id"] for hit in hits] == ["high"]


def test_opensearch_sparse_store_fake_indexes_searches_and_syncs_payload_state():
    store = OpenSearchSparseStore(config={"fake": True, "index_name": "knowmate-test"})
    store.test_connection()
    store.upsert_chunks(
        vectors=[[], []],
        payloads=[
            {
                "chunk_id": "chunk-refund",
                "knowledge_id": "doc-refund",
                "knowledge_base_id": "kb-1",
                "content": "退款政策支持七天无理由退款",
                "search_text": "refund policy 七天 退款",
                "title": "退款文档",
                "is_enabled": True,
                "metadata": {"section": "policy"},
            },
            {
                "chunk_id": "chunk-shipping",
                "knowledge_id": "doc-shipping",
                "knowledge_base_id": "kb-1",
                "content": "发货通常需要两个工作日",
                "search_text": "shipping delivery 发货",
                "title": "发货文档",
                "is_enabled": True,
            },
        ],
    )

    hits = store.search_text(knowledge_base_id="kb-1", query="refund policy", limit=5)

    assert [hit["chunk_id"] for hit in hits] == ["chunk-refund"]
    assert hits[0]["score"] > 0
    assert hits[0]["metadata"]["section"] == "policy"

    store.set_enabled_for_chunk_ids(chunk_ids=["chunk-refund"], is_enabled=False)
    assert store.search_text(knowledge_base_id="kb-1", query="refund policy", limit=5) == []

    store.set_enabled_for_chunk_ids(chunk_ids=["chunk-refund"], is_enabled=True)
    store.set_tag_for_knowledge_ids(knowledge_ids=["doc-refund"], tag_id="tag-policy")
    store.set_payload_for_chunk_ids(chunk_ids=["chunk-refund"], payload={"metadata": {"section": "updated"}})
    tagged = store.search_text(knowledge_base_id="kb-1", query="refund", limit=5)[0]
    assert tagged["tag_id"] == "tag-policy"
    assert tagged["metadata"]["section"] == "updated"

    store.move_knowledge_to_kb(knowledge_id="doc-refund", target_kb_id="kb-2")
    assert store.search_text(knowledge_base_id="kb-1", query="refund", limit=5) == []
    assert store.search_text(knowledge_base_id="kb-2", query="refund", limit=5)[0]["chunk_id"] == "chunk-refund"

    store.delete_by_knowledge_id("doc-refund")
    assert store.search_text(knowledge_base_id="kb-2", query="refund", limit=5) == []


def test_opensearch_sparse_store_requires_configuration_without_fake_client():
    store = OpenSearchSparseStore(config={})

    try:
        store.test_connection()
    except ValueError as exc:
        assert "OpenSearch/Elasticsearch sparse 检索服务未配置" in str(exc)
    else:
        raise AssertionError("expected unconfigured OpenSearch sparse store to fail clearly")
