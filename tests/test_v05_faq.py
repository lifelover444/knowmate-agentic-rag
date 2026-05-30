from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import Chunk, FAQEntry, Knowledge


def _create_faq_kb(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "FAQ KB",
            "kb_type": "faq",
            "summary_model_id": chat_id,
            "embedding_model_id": embedding_id,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["kb_type"] == "faq"
    return response.json()["id"]


def test_faq_entry_indexes_through_chunks_and_vector_store(client: TestClient, db_session, fake_vector_store):
    kb_id = _create_faq_kb(client)

    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/faqs",
        json={
            "question": "知友支持什么知识库？",
            "answer": "知友支持文档知识库和 FAQ 知识库。",
            "metadata": {"category": "product"},
            "enabled": True,
        },
    )

    assert response.status_code == 201, response.text
    faq = response.json()
    assert faq["enabled"] is True
    assert faq["metadata"] == {"category": "product"}

    entry = db_session.get(FAQEntry, faq["id"])
    assert entry is not None
    knowledge_id = entry.knowledge_id
    knowledge = db_session.get(Knowledge, knowledge_id)
    assert knowledge.type == "faq"
    assert knowledge.source_type == "faq"
    chunk = db_session.query(Chunk).filter_by(knowledge_id=knowledge_id).one()
    assert "知友支持文档知识库和 FAQ 知识库" in chunk.content
    assert chunk.chunk_metadata["faq_entry_id"] == faq["id"]

    assert fake_vector_store.points
    assert fake_vector_store.points[0]["payload"]["source_type"] == "faq"
    assert fake_vector_store.points[0]["payload"]["metadata"]["category"] == "product"

    search_response = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "FAQ 知识库", "mode": "keyword_only"},
    )
    assert search_response.status_code == 200, search_response.text
    assert search_response.json()["hits"][0]["document_id"] == knowledge_id


def test_disabling_faq_entry_removes_it_from_search(client: TestClient, fake_vector_store):
    kb_id = _create_faq_kb(client)
    faq = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/faqs",
        json={
            "question": "如何停用 FAQ？",
            "answer": "将 FAQ 条目设为停用即可。",
            "enabled": True,
        },
    ).json()

    update_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/faqs/{faq['id']}",
        json={"enabled": False},
    )

    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["enabled"] is False
    assert fake_vector_store.results == []
    search_response = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "停用 FAQ", "mode": "keyword_only"},
    )
    assert search_response.status_code == 200
    assert search_response.json()["hits"] == []
