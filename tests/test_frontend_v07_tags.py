from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_exposes_v07_tag_management_workflow():
    app = frontend_source()

    assert "KnowledgeTagRead" in app
    assert "loadTags" in app
    assert "createTag" in app
    assert "assignDocumentTags" in app
    assert "assignFaqTags" in app
    assert "/knowledge-bases/${kbId}/tags" in app
    assert "/knowledge-bases/${kbId}/documents/tags" in app
    assert "/knowledge-bases/${kbId}/faqs/tags" in app
    assert "tag_id" in app
    assert "标签筛选" in app
    assert "批量设置标签" in app
    assert "FAQ 标签" in app
    assert "未分类" in app
