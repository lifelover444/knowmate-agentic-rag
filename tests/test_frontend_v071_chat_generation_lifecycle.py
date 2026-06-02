from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_exposes_stop_generation_and_last_request_state():
    app = frontend_source()

    assert "stopGeneration" in app
    assert "/chat-sessions/${sessionId}/stop" in app
    assert "停止生成" in app
    assert "data-testid=\"stop-generation\"" in app
    assert "stopped" in app
    assert "用户已停止生成" in app

    assert "last_request_state" in app
    assert "last-request-state" in app
    assert "最后一次请求" in app
    assert "knowledge_base_ids" in app
    assert "duration_ms" in app
    assert "耗时" in app
