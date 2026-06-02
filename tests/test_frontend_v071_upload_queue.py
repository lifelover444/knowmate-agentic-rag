from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_task_020_frontend_supports_multi_file_upload_queue():
    upload_component = read("frontend/src/components/DocumentUpload.vue")
    documents_view = read("frontend/src/views/DocumentsView.vue")

    assert "multiple" in upload_component
    assert "selectedFiles" in upload_component
    assert "upload: [files: File[]]" in upload_component
    assert "Array.from(input.files || [])" in upload_component
    assert "@upload=\"uploadFiles\"" in documents_view

    assert "type UploadQueueStatus" in documents_view
    assert "const uploadQueue = ref<UploadQueueItem[]>([])" in documents_view
    assert "pending: \"等待上传\"" in documents_view
    assert "uploading: \"上传中\"" in documents_view
    assert "queued: \"已入队解析\"" in documents_view
    assert "processing: \"解析中\"" in documents_view
    assert "completed: \"解析完成\"" in documents_view
    assert "failed: \"失败\"" in documents_view

    assert "data-testid=\"upload-queue\"" in documents_view
    assert "data-testid=\"upload-queue-item\"" in documents_view
    assert "queueItem.documentId" in documents_view
    assert "queueItem.taskId" in documents_view
    assert "queueItem.errorMessage" in documents_view
    assert "上传失败" in documents_view
    assert "解析失败" in documents_view
    assert "部分成功" in documents_view
