from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frontend_exposes_parser_and_chunking_settings():
    app = (ROOT / "frontend" / "src" / "App.vue").read_text(encoding="utf-8")

    assert "解析与切分设置" in app
    assert "/parser-engines" in app
    assert "/chunker/preview" in app
    assert "parser_engine_rules" in app
    assert "enable_parent_child" in app
    assert "previewResult" in app
