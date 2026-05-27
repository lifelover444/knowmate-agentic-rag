from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_exposes_parser_and_chunking_settings():
    app = frontend_source()

    assert "切分配置" in app
    assert "/parser-engines" in app
    assert "/chunker/preview" in app
    assert "parser_engine_rules" in app
    assert "enable_parent_child" in app
    assert "previewResult" in app
