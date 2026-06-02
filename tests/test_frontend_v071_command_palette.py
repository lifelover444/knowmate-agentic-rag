from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_exposes_command_palette_minimum_workflow_entries():
    app = frontend_source()

    assert "CommandPalette" in app
    assert "command-palette" in app
    assert "data-testid=\"open-command-palette\"" in app
    assert "Ctrl+K" in app
    assert "Meta+K" in app or "event.metaKey" in app
    assert "commandPaletteQuery" in app
    assert "filteredCommands" in app

    for label in ["快速问答", "知识库", "文档管理", "FAQ 管理", "模型配置", "检索设置", "解析器状态", "存储状态"]:
        assert label in app

    for target in [
        "/chat",
        "/knowledge-bases",
        "section: \"models\"",
        "section: \"retrieval\"",
        "section: \"parser\"",
        "section: \"storage\"",
    ]:
        assert target in app
