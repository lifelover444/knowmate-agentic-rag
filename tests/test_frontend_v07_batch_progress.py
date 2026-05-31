from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_task_007_frontend_shows_batch_progress_failures_and_retry():
    view = read("frontend/src/views/DocumentsView.vue")
    store = read("frontend/src/stores/knowledgeBase.ts")
    types = read("frontend/src/types/api.ts")

    assert "BatchDocumentResponse" in types
    assert "TaskBatchSummary" in types
    assert "batchOperationResult" in store
    assert "batchDeleteDocuments" in store
    assert "batchReprocessDocuments" in store
    assert "批处理进度" in view
    assert "成功 {{ kbStore.batchOperationResult.succeeded }} 项" in view
    assert "失败 {{ kbStore.batchOperationResult.failed }} 项" in view
    assert "失败原因" in view
    assert "retryTask" in view
    assert "重试失败任务" in view
    assert "task.batch_summary" in view
