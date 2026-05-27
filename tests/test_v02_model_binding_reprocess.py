from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.models import Base, Chunk, Knowledge, ModelConfig
from app.main import create_app
from app.services.document_processing import DocumentProcessingService


class FakeModelTester:
    def test(self, config):
        return {
            "chat_ok": True,
            "embedding_ok": True,
            "detected_dimension": config.embedding_dimension,
            "message": "连接测试通过",
        }


class TypedModelTester:
    def __init__(self) -> None:
        self.chat_calls = 0
        self.embedding_calls = 0
        self.seen_api_keys: list[str] = []

    def test_chat(self, config):
        self.chat_calls += 1
        self.seen_api_keys.append(config.api_key)
        return {"chat_ok": True, "embedding_ok": True, "detected_dimension": None, "message": "对话模型测试通过"}

    def test_embedding(self, config):
        self.embedding_calls += 1
        self.seen_api_keys.append(config.api_key)
        return {
            "chat_ok": True,
            "embedding_ok": True,
            "detected_dimension": config.embedding_dimension,
            "message": "向量模型测试通过",
        }


class TrackingEmbedder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [1.0, 0.0, 0.0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        self.calls.extend(texts)
        return [[1.0, 0.0, 0.0] for _ in texts]


class TrackingChatModel:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        return "v0.2 answer"


class TrackingVectorStore:
    def __init__(self) -> None:
        self.points: list[dict] = []
        self.results: list[dict] = []
        self.deleted_knowledge_ids: list[str] = []

    def upsert_chunks(self, *, vectors: list[list[float]], payloads: list[dict]) -> None:
        self.points.extend(
            {"vector": vector, "payload": payload}
            for vector, payload in zip(vectors, payloads, strict=True)
        )
        self.results = [
            {
                "chunk_id": payload["chunk_id"],
                "knowledge_id": payload["knowledge_id"],
                "knowledge_base_id": payload["knowledge_base_id"],
                "content": payload["content"],
                "context_header": payload.get("context_header"),
                "parent_chunk_id": payload.get("parent_chunk_id"),
                "chunk_type": payload.get("chunk_type"),
                "metadata": payload.get("metadata") or {},
                "title": payload.get("title"),
                "score": 0.9,
            }
            for payload in payloads
        ]

    def delete_by_knowledge_id(self, knowledge_id: str) -> None:
        self.deleted_knowledge_ids.append(knowledge_id)
        self.points = [item for item in self.points if item["payload"]["knowledge_id"] != knowledge_id]
        self.results = [item for item in self.results if item["knowledge_id"] != knowledge_id]

    def search(
        self,
        *,
        knowledge_base_id: str,
        query_vector: list[float],
        limit: int,
        score_threshold: float | None = None,
    ):
        hits = [item for item in self.results if item["knowledge_base_id"] == knowledge_base_id]
        if score_threshold is not None:
            hits = [item for item in hits if item["score"] >= score_threshold]
        return hits[:limit]


def make_client(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'v02.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    vector_store = TrackingVectorStore()
    embedder = TrackingEmbedder()
    chat_model = TrackingChatModel()
    app = create_app(
        settings=Settings(
            database_url="sqlite://",
            upload_dir=tmp_path,
            celery_broker_url="memory://",
            celery_result_backend="cache+memory://",
            model_config_encryption_key=Fernet.generate_key().decode("ascii"),
        ),
        embedder=embedder,
        chat_model=chat_model,
        session_factory=session_factory,
        vector_store=vector_store,
        model_tester=FakeModelTester(),
    )
    return TestClient(app), session_factory, vector_store


def create_model(client: TestClient, model_type: str, model_name: str, *, dimension: int | None = None) -> str:
    payload = {
        "name": f"{model_type} model",
        "type": model_type,
        "provider": "qwen",
        "source": "remote",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "sk-secret-1234",
        "model_name": model_name,
    }
    if dimension:
        payload["embedding_dimension"] = dimension
    response = client.post("/api/v1/models", json=payload)
    assert response.status_code == 201, response.text
    assert "sk-secret-1234" not in response.text
    return response.json()["id"]


def test_models_crud_encrypts_credentials_and_filters_by_type(tmp_path: Path):
    client, session_factory, _ = make_client(tmp_path)

    chat_id = create_model(client, "KnowledgeQA", "qwen-plus")
    embedding_id = create_model(client, "Embedding", "text-embedding-v4", dimension=3)

    embedding_response = client.get("/api/v1/models", params={"type": "Embedding"})
    assert embedding_response.status_code == 200
    models = embedding_response.json()
    assert [item["id"] for item in models] == [embedding_id]
    assert models[0]["api_key_configured"] is True
    assert models[0]["api_key_last4"] == "1234"
    assert models[0]["model_name"] == "text-embedding-v4"

    with session_factory() as session:
        rows = session.execute(select(ModelConfig)).scalars().all()
        assert len(rows) == 2
        assert all(row.api_key_encrypted != "sk-secret-1234" for row in rows)

    delete_response = client.delete(f"/api/v1/models/{chat_id}")
    assert delete_response.status_code == 204


def test_model_test_endpoint_is_not_shadowed_by_model_id_route(tmp_path: Path):
    client, _, _ = make_client(tmp_path)

    response = client.post(
        "/api/v1/models/test",
        json={
            "name": "Test Embedding",
            "type": "Embedding",
            "provider": "qwen",
            "source": "remote",
            "base_url": "https://example.com/v1",
            "api_key": "sk-test",
            "model_name": "text-embedding-v4",
            "embedding_dimension": 3,
        },
    )

    assert response.status_code == 200
    assert response.json()["embedding_ok"] is True


def test_model_test_endpoint_tests_only_requested_model_type(tmp_path: Path):
    client, _, _ = make_client(tmp_path)
    tester = TypedModelTester()
    client.app.state.model_tester = tester

    qa_response = client.post(
        "/api/v1/models/test",
        json={
            "name": "DeepSeek QA",
            "type": "KnowledgeQA",
            "provider": "deepseek",
            "source": "remote",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "sk-deepseek",
            "model_name": "deepseek-chat",
        },
    )
    embedding_response = client.post(
        "/api/v1/models/test",
        json={
            "name": "Qwen Embedding",
            "type": "Embedding",
            "provider": "qwen",
            "source": "remote",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "sk-qwen",
            "model_name": "text-embedding-v4",
            "embedding_dimension": 1024,
        },
    )

    assert qa_response.status_code == 200
    assert embedding_response.status_code == 200
    assert tester.chat_calls == 1
    assert tester.embedding_calls == 1


def test_model_test_endpoint_can_use_saved_credentials_when_api_key_is_blank(tmp_path: Path):
    client, _, _ = make_client(tmp_path)
    tester = TypedModelTester()
    client.app.state.model_tester = tester
    qa_id = create_model(client, "KnowledgeQA", "deepseek-chat")
    embedding_id = create_model(client, "Embedding", "text-embedding-v4", dimension=3)

    qa_response = client.post(
        "/api/v1/models/test",
        json={
            "model_id": qa_id,
            "name": "DeepSeek QA",
            "type": "KnowledgeQA",
            "provider": "deepseek",
            "source": "remote",
            "base_url": "https://api.deepseek.com/v1",
            "model_name": "deepseek-chat",
        },
    )
    embedding_response = client.post(
        "/api/v1/models/test",
        json={
            "model_id": embedding_id,
            "name": "Qwen Embedding",
            "type": "Embedding",
            "provider": "qwen",
            "source": "remote",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model_name": "text-embedding-v4",
            "embedding_dimension": 3,
        },
    )

    assert qa_response.status_code == 200
    assert embedding_response.status_code == 200
    assert tester.chat_calls == 1
    assert tester.embedding_calls == 1
    assert tester.seen_api_keys == ["sk-secret-1234", "sk-secret-1234"]


def test_knowledge_base_requires_bound_models_and_quick_answer_uses_retrieval_threshold(tmp_path: Path):
    client, _, vector_store = make_client(tmp_path)
    chat_id = create_model(client, "KnowledgeQA", "qwen-plus")
    embedding_id = create_model(client, "Embedding", "text-embedding-v4", dimension=3)

    missing_model_response = client.post("/api/v1/knowledge-bases", json={"name": "missing models"})
    assert missing_model_response.status_code == 400

    kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "v0.2 KB",
            "embedding_model_id": embedding_id,
            "summary_model_id": chat_id,
        },
    )
    assert kb_response.status_code == 201
    kb_id = kb_response.json()["id"]
    assert kb_response.json()["embedding_model_id"] == embedding_id
    assert kb_response.json()["summary_model_id"] == chat_id

    config_response = client.put(
        "/api/v1/retrieval-config",
        json={"embedding_top_k": 50, "vector_threshold": 0.95, "rerank_top_k": 10},
    )
    assert config_response.status_code == 200

    vector_store.results = [
        {
            "chunk_id": "chunk-low",
            "knowledge_id": "doc-1",
            "knowledge_base_id": kb_id,
            "content": "低分内容",
            "score": 0.9,
        }
    ]
    answer_response = client.post("/api/v1/quick-answer", json={"knowledge_base_id": kb_id, "query": "问题"})
    assert answer_response.status_code == 200
    assert answer_response.json()["sources"] == []


def test_document_and_knowledge_base_reprocess_clear_old_vectors(tmp_path: Path, monkeypatch):
    client, session_factory, vector_store = make_client(tmp_path)
    chat_id = create_model(client, "KnowledgeQA", "qwen-plus")
    embedding_id = create_model(client, "Embedding", "text-embedding-v4", dimension=3)

    kb_id = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "reprocess KB", "embedding_model_id": embedding_id, "summary_model_id": chat_id},
    ).json()["id"]

    def run_processing_now(document_id: str) -> None:
        with session_factory() as session:
            DocumentProcessingService(
                db=session,
                upload_dir=tmp_path,
                settings=client.app.state.settings,
                embedder=client.app.state.embedder,
                vector_store=vector_store,
            ).process(document_id)

    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", run_processing_now)

    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/file",
        files={"file": ("intro.txt", b"Knowmate v0.2 rebuilds vectors.", "text/plain")},
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    reprocess_response = client.post(f"/api/v1/documents/{document_id}/reprocess")
    assert reprocess_response.status_code == 202
    assert document_id in vector_store.deleted_knowledge_ids

    kb_reprocess_response = client.post(f"/api/v1/knowledge-bases/{kb_id}/reprocess")
    assert kb_reprocess_response.status_code == 202
    assert kb_reprocess_response.json()["queued"] == 1

    with session_factory() as session:
        document = session.get(Knowledge, document_id)
        assert document.embedding_model_id == embedding_id
        assert session.query(Chunk).filter_by(knowledge_id=document_id).count() == 1
