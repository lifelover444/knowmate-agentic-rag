from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_exposes_weknora_like_kb_detail_shell():
    app = frontend_source()

    assert "KnowledgeBaseDetailView.vue" in app
    assert 'path: "/knowledge-bases/:kbId"' in app
    assert "WeKnora-like KB 详情" in app
    assert "defaultSection" in app
    assert "activeSection" in app

    assert "DocumentsView" in app
    assert "FAQView" in app
    assert "document KB 默认展示文档管理" in app
    assert "FAQ KB 默认展示 FAQ 管理" in app

    assert "概览" in app
    assert "文档管理" in app
    assert "FAQ 管理" in app
    assert "设置" in app
    assert "任务/状态" in app
    assert "Wiki 未启用" in app
    assert "Graph 未启用" in app
    assert "未实现能力暂不可进入" in app

    assert "`/knowledge-bases/${created.id}`" in app
    assert "`/knowledge-bases/${record.id}`" in app
    assert "`/knowledge-bases/${kbId}/documents`" in app
    assert "`/knowledge-bases/${kbId}/faqs`" in app
