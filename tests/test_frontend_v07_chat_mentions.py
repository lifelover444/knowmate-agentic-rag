from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_chat_mentions_submit_multi_scope_and_show_sources():
    app = frontend_source()

    assert "MentionSelector" in app
    assert "selectedMentionKbIds" in app
    assert "selectedMentionDocumentIds" in app
    assert "mentionedItems" in app
    assert "mention-chip" in app
    assert "清除范围" in app
    assert "选择范围加载失败" in app

    assert "knowledge_base_ids" in app
    assert "knowledge_ids" in app
    assert "mentioned_items" in app
    assert "params.knowledge_base_ids" in app
    assert "params.knowledge_ids" in app
    assert "params.mentioned_items" in app

    assert "source.knowledge_base_name" in app
    assert "真实来源" in app
    assert "没有选择 scope 时保留当前单 KB 默认行为" in app
