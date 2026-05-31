from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import Chunk, FAQEntry, Knowledge


def _create_document_kb(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "tag document KB",
            "summary_model_id": chat_id,
            "embedding_model_id": embedding_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_faq_kb(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "tag FAQ KB",
            "kb_type": "faq",
            "summary_model_id": chat_id,
            "embedding_model_id": embedding_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_knowledge_base_tags_crud_stats_and_duplicate_validation(client: TestClient):
    kb_id = _create_document_kb(client)

    create_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/tags",
        json={"name": "产品资料", "color": "#2563eb", "sort_order": 10},
    )
    assert create_response.status_code == 201, create_response.text
    tag = create_response.json()
    assert tag["knowledge_base_id"] == kb_id
    assert tag["name"] == "产品资料"
    assert tag["knowledge_count"] == 0
    assert tag["chunk_count"] == 0

    duplicate_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/tags",
        json={"name": "产品资料"},
    )
    assert duplicate_response.status_code == 409
    assert "标签名称已存在" in duplicate_response.text

    update_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/tags/{tag['id']}",
        json={"name": "产品手册", "color": "#16a34a", "sort_order": 1},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["name"] == "产品手册"
    assert update_response.json()["color"] == "#16a34a"

    list_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/tags", params={"keyword": "产品"})
    assert list_response.status_code == 200
    assert [item["name"] for item in list_response.json()] == ["产品手册"]


def test_document_tags_can_be_assigned_removed_and_used_as_list_filter(client: TestClient, db_session, monkeypatch):
    kb_id = _create_document_kb(client)
    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", lambda document_id: None)
    tag = client.post(f"/api/v1/knowledge-bases/{kb_id}/tags", json={"name": "合同"}).json()
    first = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/text",
        json={"title": "合同 A", "content": "甲方合同内容", "format": "text"},
    ).json()
    second = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/text",
        json={"title": "说明 B", "content": "普通说明内容", "format": "text"},
    ).json()
    db_session.add(
        Chunk(
            tenant_id=10000,
            knowledge_base_id=kb_id,
            knowledge_id=first["id"],
            content="甲方合同内容",
            search_text="甲方合同内容",
            chunk_index=0,
            start_at=0,
            end_at=6,
        )
    )
    db_session.commit()

    assign_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/documents/tags",
        json={"updates": {first["id"]: tag["id"]}},
    )
    assert assign_response.status_code == 200, assign_response.text
    assert assign_response.json() == {"updated": 1}
    assert db_session.get(Knowledge, first["id"]).tag_id == tag["id"]
    assert db_session.query(Chunk).filter_by(knowledge_id=first["id"]).one().tag_id == tag["id"]

    filtered = client.get(f"/api/v1/knowledge-bases/{kb_id}/documents", params={"tag_id": tag["id"]})
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()] == [first["id"]]
    all_document_ids = {item["id"] for item in client.get(f"/api/v1/knowledge-bases/{kb_id}/documents").json()}
    assert all_document_ids == {first["id"], second["id"]}

    remove_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/documents/tags",
        json={"updates": {first["id"]: None}},
    )
    assert remove_response.status_code == 200
    assert db_session.get(Knowledge, first["id"]).tag_id is None
    assert db_session.query(Chunk).filter_by(knowledge_id=first["id"]).one().tag_id is None


def test_faq_tags_can_be_assigned_and_are_written_to_chunks_and_vectors(
    client: TestClient,
    db_session,
    fake_vector_store,
):
    kb_id = _create_faq_kb(client)
    tag = client.post(f"/api/v1/knowledge-bases/{kb_id}/tags", json={"name": "售后"}).json()
    faq = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/faqs",
        json={"question": "怎么退货？", "answer": "联系售后处理。"},
    ).json()

    assign_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/faqs/tags",
        json={"updates": {faq["id"]: tag["id"]}},
    )
    assert assign_response.status_code == 200, assign_response.text
    assert assign_response.json() == {"updated": 1}

    entry = db_session.get(FAQEntry, faq["id"])
    assert entry.tag_id == tag["id"]
    assert db_session.get(Knowledge, entry.knowledge_id).tag_id == tag["id"]
    chunk = db_session.query(Chunk).filter_by(knowledge_id=entry.knowledge_id).one()
    assert chunk.tag_id == tag["id"]
    assert fake_vector_store.points[-1]["payload"]["tag_id"] == tag["id"]

    filtered = client.get(f"/api/v1/knowledge-bases/{kb_id}/faqs", params={"tag_id": tag["id"]})
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()] == [faq["id"]]

    tag_stats = client.get(f"/api/v1/knowledge-bases/{kb_id}/tags").json()[0]
    assert tag_stats["knowledge_count"] == 1
    assert tag_stats["chunk_count"] == 1


def test_deleting_referenced_tag_requires_removing_assignments_first(client: TestClient, monkeypatch):
    kb_id = _create_document_kb(client)
    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", lambda document_id: None)
    tag = client.post(f"/api/v1/knowledge-bases/{kb_id}/tags", json={"name": "法规"}).json()
    document = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/text",
        json={"title": "法规条文", "content": "法规内容", "format": "text"},
    ).json()
    client.put(f"/api/v1/knowledge-bases/{kb_id}/documents/tags", json={"updates": {document["id"]: tag["id"]}})

    delete_response = client.delete(f"/api/v1/knowledge-bases/{kb_id}/tags/{tag['id']}")
    assert delete_response.status_code == 400
    assert "标签仍有文档或 FAQ 引用" in delete_response.text

    client.put(f"/api/v1/knowledge-bases/{kb_id}/documents/tags", json={"updates": {document["id"]: None}})
    delete_response = client.delete(f"/api/v1/knowledge-bases/{kb_id}/tags/{tag['id']}")
    assert delete_response.status_code == 204
    assert client.get(f"/api/v1/knowledge-bases/{kb_id}/tags").json() == []
