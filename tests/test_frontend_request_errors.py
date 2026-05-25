from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frontend_request_handles_non_json_error_responses():
    app = (ROOT / "frontend" / "src" / "App.vue").read_text(encoding="utf-8")

    assert "function parseResponsePayload" in app
    assert "JSON.parse(text)" in app
    assert "catch" in app
    assert "formatApiError(payload, text || `HTTP ${response.status}`)" in app
