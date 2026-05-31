from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_exposes_v06_sessions_streaming_and_trace():
    app = frontend_source()

    assert "/chat-sessions" in app
    assert "/quick-answer/stream" in app
    assert "postSse" in app
    assert "ReadableStream" in app or "getReader" in app
    assert "chat-session-list" in app
    assert "chat-message-list" in app
    assert "enable-query-rewrite" in app
    assert "message-trace" in app
    assert "knowledge-search-panel" in app
    assert "html: false" in app
