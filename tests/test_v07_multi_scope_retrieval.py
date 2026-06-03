from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import Chunk, Knowledge


def create_kb(client: TestClient, name: str, chat_id: str, embedding_id: str) -> str:
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": name, "summary_model_id": chat_id, "embedding_model_id": embedding_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add_document_chunk(db_session, kb_id: str, document_id: str, title: str, chunk_id: str, content: str) -> None:
    db_session.add(
        Knowledge(
            id=document_id,
            tenant_id=10000,
            knowledge_base_id=kb_id,
            type="file",
            title=title,
            source="upload",
            parse_status="completed",
            enable_status="enabled",
            file_size=0,
            storage_size=0,
        )
    )
    db_session.add(
        Chunk(
            id=chunk_id,
            tenant_id=10000,
            knowledge_base_id=kb_id,
            knowledge_id=document_id,
            content=content,
            search_text=content,
            chunk_index=0,
            start_at=0,
            end_at=len(content),
            chunk_metadata={"title": title},
        )
    )
    db_session.commit()


def test_knowledge_search_supports_multi_kb_scope_and_returns_kb_name(client: TestClient, db_session):
    chat_id, embedding_id = create_bound_models(client)
    first_kb = create_kb(client, "产品知识库", chat_id, embedding_id)
    second_kb = create_kb(client, "运维知识库", chat_id, embedding_id)
    add_document_chunk(db_session, first_kb, "doc-product", "产品手册", "chunk-product", "范围检索 产品")
    add_document_chunk(db_session, second_kb, "doc-ops", "运维手册", "chunk-ops", "范围检索 运维")

    response = client.post(
        "/api/v1/knowledge-search",
        json={
            "knowledge_base_ids": [first_kb, second_kb],
            "query": "范围检索",
            "mode": "keyword_only",
            "top_k": 5,
        },
    )

    assert response.status_code == 200, response.text
    hits = response.json()["hits"]
    assert {hit["knowledge_base_id"] for hit in hits} == {first_kb, second_kb}
    assert {hit["knowledge_base_name"] for hit in hits} == {"产品知识库", "运维知识库"}
    assert {hit["document_id"] for hit in hits} == {"doc-product", "doc-ops"}
    retrievers = response.json()["diagnostics"]["retrievers"]
    assert len(retrievers) == 2
    assert {item["knowledge_base_id"] for item in retrievers} == {first_kb, second_kb}
    assert {item["engine"] for item in retrievers} == {"qdrant+postgres"}
    assert all(item["status"] == "done" for item in retrievers)
    assert all(item["hit_count"] == 1 for item in retrievers)


def test_knowledge_search_supports_file_scope_without_explicit_kb(client: TestClient, db_session):
    chat_id, embedding_id = create_bound_models(client)
    kb_id = create_kb(client, "文件范围知识库", chat_id, embedding_id)
    add_document_chunk(db_session, kb_id, "doc-a", "A 文档", "chunk-a", "文件范围 命中")
    add_document_chunk(db_session, kb_id, "doc-b", "B 文档", "chunk-b", "文件范围 不应命中")

    response = client.post(
        "/api/v1/knowledge-search",
        json={
            "knowledge_ids": ["doc-a"],
            "query": "文件范围",
            "mode": "keyword_only",
            "top_k": 5,
        },
    )

    assert response.status_code == 200, response.text
    hits = response.json()["hits"]
    assert [hit["document_id"] for hit in hits] == ["doc-a"]


def test_quick_answer_supports_multi_kb_scope(client: TestClient, db_session):
    chat_id, embedding_id = create_bound_models(client)
    first_kb = create_kb(client, "问答产品库", chat_id, embedding_id)
    second_kb = create_kb(client, "问答运维库", chat_id, embedding_id)
    add_document_chunk(db_session, first_kb, "qa-doc-product", "产品问答", "qa-chunk-product", "多库问答 产品")
    add_document_chunk(db_session, second_kb, "qa-doc-ops", "运维问答", "qa-chunk-ops", "多库问答 运维")

    response = client.post(
        "/api/v1/quick-answer",
        json={
            "knowledge_base_ids": [first_kb, second_kb],
            "query": "多库问答",
            "mode": "keyword_only",
            "top_k": 5,
        },
    )

    assert response.status_code == 200, response.text
    sources = response.json()["sources"]
    assert {source["knowledge_base_id"] for source in sources} == {first_kb, second_kb}
    assert {source["knowledge_base_name"] for source in sources} == {"问答产品库", "问答运维库"}


def test_search_scope_requires_kb_or_file_scope(client: TestClient):
    response = client.post("/api/v1/knowledge-search", json={"query": "没有 scope"})

    assert response.status_code == 400
    assert "至少提供一个 knowledge_base_id、knowledge_base_ids 或 knowledge_ids" in response.text


def test_multi_kb_scope_rejects_different_embedding_models(client: TestClient):
    chat_id, embedding_id = create_bound_models(client)
    next_chat_id, next_embedding_id = create_bound_models(client)
    first_kb = create_kb(client, "模型 A", chat_id, embedding_id)
    second_kb = create_kb(client, "模型 B", next_chat_id, next_embedding_id)

    response = client.post(
        "/api/v1/knowledge-search",
        json={
            "knowledge_base_ids": [first_kb, second_kb],
            "query": "模型冲突",
            "mode": "keyword_only",
        },
    )

    assert response.status_code == 400
    assert "跨知识库检索要求使用相同 Embedding 模型" in response.text
