from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import httpx
from conftest import create_bound_models
from pypdf import PdfReader, PdfWriter

from app.db.models import Knowledge
from app.integrations.mineru import MinerUError, MinerUParseResult, _safe_data_id
from app.services.document_processing import DocumentProcessingService
from app.services.knowledge_base import default_parser_engine_rules


def _pdf_bytes(page_count: int) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_parser_config_api_saves_mineru_key_without_echoing(client):
    response = client.put(
        "/api/v1/parser-configs/mineru",
        json={
            "name": "MinerU",
            "base_url": "https://mineru.net/api/v4",
            "api_key": "mineru-secret-1234",
            "status": "active",
            "config": {
                "model_version": "vlm",
                "language": "ch",
                "enable_table": True,
                "enable_formula": True,
                "is_ocr": False,
            },
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["provider"] == "mineru"
    assert payload["api_key_configured"] is True
    assert payload["api_key_last4"] == "1234"
    assert "mineru-secret-1234" not in response.text

    get_response = client.get("/api/v1/parser-configs/mineru")
    assert get_response.status_code == 200, get_response.text
    assert "mineru-secret-1234" not in get_response.text
    assert get_response.json()["config"]["model_version"] == "vlm"


def test_default_parser_rules_use_mineru_for_document_formats():
    rules = default_parser_engine_rules()
    engine_by_type = {
        file_type: rule["engine"]
        for rule in rules
        for file_type in rule["file_types"]
    }

    for file_type in ["pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "png", "jpg", "jpeg", "webp", "bmp"]:
        assert engine_by_type[file_type] == "mineru"
    for file_type in ["txt", "md", "markdown", "csv", "json"]:
        assert engine_by_type[file_type] == "builtin"


def test_mineru_data_id_only_contains_supported_ascii_characters():
    data_id = _safe_data_id(Path("doc-id_中华人民共和国反垄断法_20220624.pdf"))

    assert data_id.startswith("doc-id_")
    assert data_id.endswith("_20220624")
    assert set(data_id) <= set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-")
    assert data_id.isascii()


def test_mineru_client_checks_cancellation_after_upload(tmp_path: Path):
    from app.integrations.mineru import MinerUClient, MinerUConfig

    source = tmp_path / "cancel.pdf"
    source.write_bytes(b"%PDF fake")
    checks = 0
    requests: list[str] = []

    class Cancelled(RuntimeError):
        pass

    def cancel_check() -> None:
        nonlocal checks
        checks += 1
        if checks == 2:
            raise Cancelled("cancel now")

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.method)
        if request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "msg": "ok",
                    "data": {"batch_id": "cancel-batch", "file_urls": ["https://upload.example/cancel.pdf"]},
                },
            )
        if request.method == "PUT":
            return httpx.Response(200)
        raise AssertionError("polling should stop before the first result request")

    client = MinerUClient(
        MinerUConfig(api_key="mineru-token", poll_interval_seconds=0),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        cancel_check=cancel_check,
    )

    try:
        client.parse_file(source)
    except Cancelled as exc:
        assert str(exc) == "cancel now"
    else:
        raise AssertionError("expected cancellation")
    assert requests == ["POST", "PUT"]


def test_mineru_client_uploads_polls_and_reads_full_markdown(tmp_path: Path):
    from app.integrations.mineru import MinerUClient, MinerUConfig

    source = tmp_path / "demo.pdf"
    source.write_bytes(b"%PDF fake")
    zip_path = tmp_path / "result.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("demo/full.md", "# MinerU\n\n解析后的 Markdown")
        archive.writestr("demo/demo_content_list.json", '[{"type":"text","page_idx":0}]')

    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        if request.method == "POST" and request.url.path.endswith("/file-urls/batch"):
            assert request.headers["authorization"] == "Bearer mineru-token"
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "msg": "ok",
                    "trace_id": "trace-submit",
                    "data": {"batch_id": "batch-1", "file_urls": ["https://upload.example/demo.pdf"]},
                },
            )
        if request.method == "PUT" and str(request.url).startswith("https://upload.example"):
            return httpx.Response(200)
        if request.method == "GET" and request.url.path.endswith("/extract-results/batch/batch-1"):
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "msg": "ok",
                    "trace_id": "trace-result",
                    "data": {
                        "batch_id": "batch-1",
                        "extract_result": [
                            {
                                "file_name": "demo.pdf",
                                "state": "done",
                                "full_zip_url": "https://cdn.example/result.zip",
                                "err_msg": "",
                            }
                        ],
                    },
                },
            )
        if request.method == "GET" and str(request.url) == "https://cdn.example/result.zip":
            return httpx.Response(200, content=zip_path.read_bytes())
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = MinerUClient(
        MinerUConfig(
            base_url="https://mineru.net/api/v4",
            api_key="mineru-token",
            model_version="vlm",
            language="ch",
            enable_table=True,
            enable_formula=True,
            is_ocr=False,
            poll_interval_seconds=0,
            poll_timeout_seconds=3,
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.parse_file(source)

    assert result.markdown == "# MinerU\n\n解析后的 Markdown"
    assert result.metadata["mineru_batch_id"] == "batch-1"
    assert result.metadata["mineru_trace_id"] == "trace-result"
    assert result.metadata["full_zip_url"] == "https://cdn.example/result.zip"
    assert result.metadata["content_list_summary"]["text"] == 1
    assert ("PUT", "https://upload.example/demo.pdf") in calls


def test_mineru_client_raises_clear_error_when_task_failed(tmp_path: Path):
    from app.integrations.mineru import MinerUClient, MinerUConfig, MinerUError

    source = tmp_path / "broken.pdf"
    source.write_bytes(b"%PDF fake")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(
                200,
                json={"code": 0, "msg": "ok", "data": {"batch_id": "batch-2", "file_urls": ["https://upload.example/broken.pdf"]}},
            )
        if request.method == "PUT":
            return httpx.Response(200)
        return httpx.Response(
            200,
            json={
                "code": 0,
                "msg": "ok",
                "data": {
                    "batch_id": "batch-2",
                    "extract_result": [{"file_name": "broken.pdf", "state": "failed", "err_msg": "文件格式不支持"}],
                },
            },
        )

    client = MinerUClient(
        MinerUConfig(
            base_url="https://mineru.net/api/v4",
            api_key="mineru-token",
            poll_interval_seconds=0,
            poll_timeout_seconds=3,
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        client.parse_file(source)
    except MinerUError as exc:
        assert "MinerU 解析失败：文件格式不支持" in str(exc)
    else:
        raise AssertionError("expected MinerUError")


def test_mineru_pdf_splitter_creates_200_page_parts(tmp_path: Path):
    from app.integrations.pdf_splitter import split_pdf_by_page_limit

    source = tmp_path / "large.pdf"
    source.write_bytes(_pdf_bytes(401))
    output_dir = tmp_path / "parts"

    parts = split_pdf_by_page_limit(source, output_dir, max_pages=200)

    assert [(part.page_start, part.page_end) for part in parts] == [(1, 200), (201, 400), (401, 401)]
    assert [len(PdfReader(str(part.path)).pages) for part in parts] == [200, 200, 1]
    assert [part.index for part in parts] == [1, 2, 3]


def test_document_processing_splits_large_pdf_before_mineru_parse(
    client,
    db_session,
    fake_embedder,
    fake_vector_store,
    monkeypatch,
    tmp_path: Path,
):
    holder = {}
    parsed_page_counts: list[int] = []

    def run_processing_now(document_id: str) -> None:
        with holder["app"].state.session_factory() as session:
            DocumentProcessingService(
                db=session,
                upload_dir=tmp_path,
                settings=holder["app"].state.settings,
                embedder=fake_embedder,
                vector_store=fake_vector_store,
            ).process(document_id)

    def fake_parse_file(self, path: Path) -> MinerUParseResult:
        page_count = len(PdfReader(str(path)).pages)
        parsed_page_counts.append(page_count)
        assert page_count <= 200
        return MinerUParseResult(
            markdown=f"分片 {len(parsed_page_counts)} 内容。" * 80,
            metadata={
                "mineru_batch_id": f"batch-{len(parsed_page_counts)}",
                "mineru_state": "done",
                "mineru_trace_id": f"trace-{len(parsed_page_counts)}",
                "full_zip_url": f"https://cdn.example/part-{len(parsed_page_counts)}.zip",
                "model_version": "vlm",
            },
        )

    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", run_processing_now)
    monkeypatch.setattr("app.integrations.mineru.MinerUClient.parse_file", fake_parse_file)
    holder["app"] = client.app
    chat_id, embedding_id = create_bound_models(client)
    config_response = client.put(
        "/api/v1/parser-configs/mineru",
        json={"name": "MinerU", "base_url": "https://mineru.net/api/v4", "api_key": "mineru-secret-1234"},
    )
    assert config_response.status_code == 200, config_response.text
    kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Large PDF KB", "summary_model_id": chat_id, "embedding_model_id": embedding_id},
    )
    assert kb_response.status_code == 201, kb_response.text
    kb_id = kb_response.json()["id"]

    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/file",
        files={"file": ("large.pdf", _pdf_bytes(401), "application/pdf")},
    )

    assert upload_response.status_code == 201, upload_response.text
    assert parsed_page_counts == [200, 200, 1]
    document = upload_response.json()
    refreshed = client.get(f"/api/v1/documents/{document['id']}").json()
    assert refreshed["parse_status"] == "completed"
    stored = db_session.get(Knowledge, document["id"])
    assert stored.doc_metadata["mineru_split"] is True
    assert stored.doc_metadata["mineru_split_part_count"] == 3
    assert stored.doc_metadata["mineru_split_max_pages"] == 200
    assert stored.doc_metadata["page_count"] == 401
    assert [part["page_start"] for part in stored.doc_metadata["mineru_parts"]] == [1, 201, 401]
    assert [part["mineru_batch_id"] for part in stored.doc_metadata["mineru_parts"]] == [
        "batch-1",
        "batch-2",
        "batch-3",
    ]
    assert fake_vector_store.points
    assert "第 201-400 页" in "\n".join(point["payload"]["search_text"] for point in fake_vector_store.points)


def test_document_processing_reports_large_pdf_split_part_failure(
    client,
    db_session,
    fake_embedder,
    fake_vector_store,
    monkeypatch,
    tmp_path: Path,
):
    holder = {}
    call_count = 0

    def run_processing_now(document_id: str) -> None:
        with holder["app"].state.session_factory() as session:
            try:
                DocumentProcessingService(
                    db=session,
                    upload_dir=tmp_path,
                    settings=holder["app"].state.settings,
                    embedder=fake_embedder,
                    vector_store=fake_vector_store,
                ).process(document_id)
            except MinerUError:
                pass

    def fake_parse_file(self, path: Path) -> MinerUParseResult:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise MinerUError("MinerU 解析失败：服务限流")
        return MinerUParseResult(
            markdown=f"分片 {call_count} 内容。" * 80,
            metadata={"mineru_batch_id": f"batch-{call_count}"},
        )

    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", run_processing_now)
    monkeypatch.setattr("app.integrations.mineru.MinerUClient.parse_file", fake_parse_file)
    holder["app"] = client.app
    chat_id, embedding_id = create_bound_models(client)
    config_response = client.put(
        "/api/v1/parser-configs/mineru",
        json={"name": "MinerU", "base_url": "https://mineru.net/api/v4", "api_key": "mineru-secret-1234"},
    )
    assert config_response.status_code == 200, config_response.text
    kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Large PDF Failure KB", "summary_model_id": chat_id, "embedding_model_id": embedding_id},
    )
    assert kb_response.status_code == 201, kb_response.text
    kb_id = kb_response.json()["id"]

    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/file",
        files={"file": ("large-failure.pdf", _pdf_bytes(401), "application/pdf")},
    )

    assert upload_response.status_code == 201, upload_response.text
    document = db_session.get(Knowledge, upload_response.json()["id"])
    assert document.parse_status == "failed"
    assert "MinerU 分片 2/3（第 201-400 页）解析失败" in document.error_message
    assert "服务限流" in document.error_message
    assert fake_vector_store.points == []


def test_document_processing_uses_mineru_parser_metadata(
    client,
    db_session,
    fake_embedder,
    fake_vector_store,
    monkeypatch,
    tmp_path: Path,
):
    holder = {}

    def run_processing_now(document_id: str) -> None:
        with holder["app"].state.session_factory() as session:
            DocumentProcessingService(
                db=session,
                upload_dir=tmp_path,
                settings=holder["app"].state.settings,
                embedder=fake_embedder,
                vector_store=fake_vector_store,
            ).process(document_id)

    def fake_parse_file(self, path: Path) -> MinerUParseResult:
        return MinerUParseResult(
            markdown="# MinerU 文档\n\n## 第一节\n\n解析后的内容。" * 80,
            metadata={
                "mineru_batch_id": "batch-doc",
                "mineru_state": "done",
                "mineru_trace_id": "trace-doc",
                "full_zip_url": "https://cdn.example/doc.zip",
                "model_version": "vlm",
            },
        )

    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", run_processing_now)
    monkeypatch.setattr("app.integrations.mineru.MinerUClient.parse_file", fake_parse_file)
    holder["app"] = client.app
    chat_id, embedding_id = create_bound_models(client)
    config_response = client.put(
        "/api/v1/parser-configs/mineru",
        json={"name": "MinerU", "base_url": "https://mineru.net/api/v4", "api_key": "mineru-secret-1234"},
    )
    assert config_response.status_code == 200, config_response.text
    kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "MinerU KB", "summary_model_id": chat_id, "embedding_model_id": embedding_id},
    )
    assert kb_response.status_code == 201, kb_response.text
    kb_id = kb_response.json()["id"]

    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/file",
        files={"file": ("mineru.pdf", _pdf_bytes(1), "application/pdf")},
    )

    assert upload_response.status_code == 201, upload_response.text
    document = upload_response.json()
    refreshed = client.get(f"/api/v1/documents/{document['id']}").json()
    assert refreshed["parse_status"] == "completed"
    stored = db_session.get(Knowledge, document["id"])
    assert stored.doc_metadata["mineru_batch_id"] == "batch-doc"
    assert stored.doc_metadata["mineru_trace_id"] == "trace-doc"
    assert fake_vector_store.points
    assert fake_vector_store.points[0]["payload"]["metadata"]["document_id"] == document["id"]
