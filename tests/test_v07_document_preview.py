from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import Chunk, Knowledge


def _create_kb(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "preview KB", "summary_model_id": chat_id, "embedding_model_id": embedding_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _add_document_with_chunks(db_session, kb_id: str, *, file_type: str, status: str = "completed") -> Knowledge:
    document = Knowledge(
        tenant_id=10000,
        knowledge_base_id=kb_id,
        type="file",
        source_type="file",
        title=f"preview.{file_type}",
        source="upload",
        parse_status=status,
        enable_status="enabled",
        file_name=f"preview.{file_type}",
        file_type=file_type,
        file_size=128,
        storage_size=128,
        doc_metadata={"summary": f"{file_type} 摘要", "pages": [{"page": 1, "text": "第一页内容"}]},
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    if status == "completed":
        db_session.add_all(
            [
                Chunk(
                    tenant_id=10000,
                    knowledge_base_id=kb_id,
                    knowledge_id=document.id,
                    content=f"{file_type} 第一段内容",
                    search_text=f"{file_type} 第一段内容",
                    chunk_index=0,
                    start_at=0,
                    end_at=20,
                    context_header="# 第一节",
                    chunk_type="text",
                ),
                Chunk(
                    tenant_id=10000,
                    knowledge_base_id=kb_id,
                    knowledge_id=document.id,
                    content=f"{file_type} 第二段内容",
                    search_text=f"{file_type} 第二段内容",
                    chunk_index=1,
                    start_at=21,
                    end_at=40,
                    context_header="# 第二节",
                    chunk_type="text",
                ),
            ]
        )
        db_session.commit()
    return document


def test_document_preview_returns_summary_content_and_chunk_outline(client: TestClient, db_session):
    kb_id = _create_kb(client)
    document = _add_document_with_chunks(db_session, kb_id, file_type="md")

    response = client.get(f"/api/v1/documents/{document.id}/preview")

    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["id"] == document.id
    assert preview["title"] == "preview.md"
    assert preview["file_type"] == "md"
    assert preview["status"] == "completed"
    assert preview["summary"] == "md 摘要"
    assert "md 第一段内容" in preview["content_preview"]
    assert "md 第二段内容" in preview["content_preview"]
    assert preview["chunks"][0]["context_header"] == "# 第一节"
    assert preview["chunks"][0]["content_preview"] == "md 第一段内容"


def test_document_preview_supports_common_parsed_file_types(client: TestClient, db_session):
    kb_id = _create_kb(client)
    document_ids = [
        _add_document_with_chunks(db_session, kb_id, file_type=file_type).id
        for file_type in ["txt", "csv", "docx", "pdf"]
    ]

    previews = [client.get(f"/api/v1/documents/{document_id}/preview").json() for document_id in document_ids]

    assert [preview["file_type"] for preview in previews] == ["txt", "csv", "docx", "pdf"]
    assert all(preview["chunks"] for preview in previews)
    assert all("第一段内容" in preview["content_preview"] for preview in previews)


def test_failed_document_preview_returns_failure_state_without_raw_exception(client: TestClient, db_session):
    kb_id = _create_kb(client)
    document = _add_document_with_chunks(db_session, kb_id, file_type="pdf", status="failed")
    document.error_message = "解析失败：测试错误"
    db_session.add(document)
    db_session.commit()

    response = client.get(f"/api/v1/documents/{document.id}/preview")

    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["status"] == "failed"
    assert preview["error_message"] == "解析失败：测试错误"
    assert preview["content_preview"] == ""
    assert preview["chunks"] == []
