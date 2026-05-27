from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_allows_large_documents_to_process_for_five_minutes():
    app = frontend_source()

    assert "documentProcessingMaxPolls = 300" in app
    assert "index < documentProcessingMaxPolls" in app
    assert "setTimeout(resolve, 1000)" in app
