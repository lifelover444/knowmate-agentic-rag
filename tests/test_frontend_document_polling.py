from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frontend_allows_large_documents_to_process_for_five_minutes():
    app = (ROOT / "frontend" / "src" / "App.vue").read_text(encoding="utf-8")

    assert "const documentProcessingMaxPolls = 300;" in app
    assert "index < documentProcessingMaxPolls" in app
    assert "await new Promise((resolve) => setTimeout(resolve, 1000));" in app
