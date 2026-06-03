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


def test_frontend_exposes_message_history_search_and_stats():
    app = frontend_source()

    assert "messageSearchQuery" in app
    assert "messageSearchResults" in app
    assert "chatHistoryStats" in app
    assert "searchMessageHistory" in app
    assert "/messages/search" in app
    assert "/messages/chat-history-stats" in app
    assert "历史问答搜索" in app
    assert "搜索历史回答" in app
    assert "暂无历史问答命中" in app
    assert "可检索消息" in app
    assert "answer_snippet" in app
