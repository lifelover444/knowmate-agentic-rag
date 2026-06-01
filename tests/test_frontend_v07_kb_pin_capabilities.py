from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_exposes_kb_pin_and_capabilities_workflow():
    app = frontend_source()

    assert "KnowledgeBaseCapabilities" in app
    assert "capabilities" in app
    assert "is_pinned" in app
    assert "pinned_at" in app
    assert "updateKnowledgeBasePin" in app
    assert '/knowledge-bases/${kbId}/pin' in app

    assert "置顶" in app
    assert "取消置顶" in app
    assert "pin-filled" in app
    assert "置顶失败" in app

    assert "能力" in app
    assert "向量" in app
    assert "关键词" in app
    assert "父子块" in app
    assert "重排" in app
    assert "Wiki 未启用" in app
    assert "Graph 未启用" in app
