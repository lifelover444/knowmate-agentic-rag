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


def test_frontend_chat_trace_uses_chinese_stage_labels_and_safe_summary():
    app = frontend_source()

    assert "traceStageLabel" in app
    assert "traceStatusText" in app
    assert "traceStageSummary" in app
    assert "mode_not_applicable" in app
    assert "不适用于当前检索模式" in app
    assert "向量检索" in app
    assert "关键词检索" in app
    assert "RRF 合并" in app
    assert "父子块扩展" in app
    assert "去重" in app
    assert "FAQ 合并" in app
    assert "重排" in app
    assert "已跳过" in app
    assert "已完成" in app
    assert "失败" in app
    assert "knowledge-search-trace" in app


def test_frontend_chat_trace_shows_prompt_context_summary():
    app = frontend_source()

    assert "promptContextSummary" in app
    assert "本次送入模型的上下文摘要" in app
    assert "prompt-context-summary" in app


def test_frontend_chat_supports_text_attachments():
    app = frontend_source()

    assert "chat-attachment-input" in app
    assert "临时附件" in app
    assert "attachments" in app
    assert "txt/md/csv/json" in app
    assert "附件内容已截断" in app
    assert "不支持的附件类型" in app
