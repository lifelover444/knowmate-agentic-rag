from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_task_017_frontend_shows_document_processing_timeline():
    types = read("frontend/src/types/api.ts")
    store = read("frontend/src/stores/knowledgeBase.ts")
    view = read("frontend/src/views/DocumentsView.vue")
    styles = read("frontend/src/styles/app.css")

    assert "ProcessingSpanRead" in types
    assert "ProcessingSpanTimeline" in types
    assert "currentProcessingTimeline" in store
    assert "loadDocumentSpans" in store
    assert "/documents/${documentId}/spans" in store
    assert "处理时间线" in view
    assert "openProcessingTimeline" in view
    assert "refreshProcessingTimeline" in view
    assert "timeline-stage" in view
    assert "timelineStageText" in view
    assert "timelineStatusText" in view
    assert "手动刷新" in view
    assert "无阶段记录时显示当前文档状态占位" in view
    assert "processing-timeline" in styles
    assert "timeline-stage--failed" in styles
    assert "timeline-stage--running" in styles
