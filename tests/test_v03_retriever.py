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
