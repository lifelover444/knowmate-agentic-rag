from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_task_021_frontend_exposes_download_cancel_and_move_actions():
    view = read("frontend/src/views/DocumentsView.vue")
    store = read("frontend/src/stores/knowledgeBase.ts")
    types = read("frontend/src/types/api.ts")

    assert "downloadDocument" in store
    assert "cancelDocumentParse" in store
    assert "moveDocuments" in store
    assert "DocumentMoveResponse" in types

    assert "downloadDocument(record)" in view
    assert "cancelDocumentParse(record)" in view
    assert "openMoveDocument(record)" in view
    assert "moveDocumentVisible" in view
    assert "targetKnowledgeBaseId" in view
    assert "提交移动" in view

    assert "下载原文件" in view
    assert "取消解析" in view
    assert "移动到知识库" in view
    assert "用户已取消解析" in view
