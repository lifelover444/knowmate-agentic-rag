from app.rag.retriever import (
    HybridRetriever,
    ParentChildExpander,
    RerankPipeline,
    RetrievalHit,
    clean_rerank_passage,
)


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
