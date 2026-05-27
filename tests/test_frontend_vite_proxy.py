from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_vite_proxies_api_requests_to_fastapi_backend():
    config = (ROOT / "frontend" / "vite.config.js").read_text(encoding="utf-8")

    assert (ROOT / "frontend" / "vite.config.js").exists()
    assert '"/api"' in config
    assert '"/health"' in config
    assert "target: backendTarget" in config
    assert "VITE_API_PROXY_TARGET" in config
    assert "http://127.0.0.1:8000" in config
    assert "changeOrigin: true" in config
