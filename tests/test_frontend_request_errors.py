from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_request_handles_non_json_error_responses():
    app = frontend_source()

    assert "parseResponsePayload" in app
    assert "JSON.parse(text)" in app
    assert "catch" in app
    assert "formatApiError(payload, text || `HTTP ${response.status}`)" in app
