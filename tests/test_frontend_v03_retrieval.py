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

    assert "retrievalMode" in app
    assert "retrievalKeywordThreshold" in app
    assert "retrievalRrfVectorWeight" in app
    assert "retrievalRrfKeywordWeight" in app
    assert "retrievalEnableRerank" in app
    assert "selectedRerankModelId" in app
    assert "/knowledge-search" in app
    assert "knowledgeSearchResult" in app
    assert "retrieval_method" in app
    assert "rerank_score" in app
