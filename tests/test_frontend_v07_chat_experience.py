from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_exposes_chat_search_batch_delete_and_recommendations():
    app = frontend_source()

    assert "sessionSearchKeyword" in app
    assert "filteredSessions" in app
    assert "chat-session-search" in app
    assert "selectedSessionIds" in app
    assert "batchDeleteSessions" in app
    assert "/chat-sessions/batch-delete" in app
    assert "批量删除" in app

    assert "recommendedQuestions" in app
    assert "loadRecommendedQuestions" in app
    assert "/chat-sessions/recommended-questions" in app
    assert "recommended-question-list" in app
    assert "推荐问题" in app
