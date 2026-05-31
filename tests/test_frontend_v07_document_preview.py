from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_exposes_v07_document_preview_drawer_and_chunk_navigation():
    app = frontend_source()

    assert "DocumentPreviewRead" in app
    assert "loadDocumentPreview" in app
    assert "/documents/${documentId}/preview" in app
    assert "文档预览" in app
    assert "preview-outline" in app
    assert "preview-content" in app
    assert "jumpToPreviewChunk" in app
    assert "content_preview" in app
