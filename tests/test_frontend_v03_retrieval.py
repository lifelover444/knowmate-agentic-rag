from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_exposes_v03_retrieval_controls_and_knowledge_search():
    app = frontend_source()
    retrieval_view = (ROOT / "frontend" / "src" / "views" / "RetrievalSettingsView.vue").read_text(encoding="utf-8")

    assert "v0.9 固定主链路" in retrieval_view
    assert "data-testid=\"retrieval-mode\"" not in retrieval_view
    assert "vector_only" not in retrieval_view
    assert "keyword_only" not in retrieval_view
    assert "data-testid=\"retrieval-enable-rerank\"" not in retrieval_view
    assert "rerank 必需" in retrieval_view
    assert "ParadeDB BM25" in retrieval_view
    assert "Qdrant" in retrieval_view
    assert "retrievalMode" not in retrieval_view
    assert "retrievalKeywordThreshold" in app
    assert "retrievalRrfVectorWeight" in app
    assert "retrievalRrfKeywordWeight" in app
    assert "selectedRerankModelId" in app
    assert "/knowledge-search" in app
    assert "knowledgeSearchResult" in app
    assert "retrieval_method" in app
    assert "rerank_score" in app


def test_frontend_vector_store_settings_use_types_api():
    app = (ROOT / "frontend" / "src" / "views" / "VectorStoreSettingsView.vue").read_text(encoding="utf-8")

    assert "Qdrant 配置状态" in app
    assert "/vector-stores/types" not in app
    assert "vectorStoreTypes" not in app
    assert "loadVectorStoreTypes" not in app
    assert "connection_fields" in app
    assert "index_fields" in app
    assert "planned" not in app
    assert "OpenSearch" not in app
    assert "Elasticsearch" not in app
    assert "Milvus" not in app
    assert "Weaviate" not in app
    assert "Doris" not in app
    assert "Tencent VectorDB" not in app
