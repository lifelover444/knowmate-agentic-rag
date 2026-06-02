from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.models import Base
from app.main import create_app


class FakeEmbedder:
    dimensions = 3

    def embed(self, text: str) -> list[float]:
        return [float(len(text) % 7), 1.0, 0.5]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


class FakeChatModel:
    def complete(self, messages: list[dict[str, str]]) -> str:
        context = messages[-1]["content"]
        marker = "Context:\n"
        if marker in context:
            return context.split(marker, 1)[1].split("\n\nQuestion:", 1)[0].strip()
        return "fake answer"


class FakeVectorStore:
    def __init__(self) -> None:
        self.points: list[dict] = []
        self.results: list[dict] = []

    def ensure_collection(self, dimension: int) -> None:
        self.dimension = dimension

    def upsert_chunks(self, *, vectors: list[list[float]], payloads: list[dict]) -> None:
        self.points.extend(
            {"vector": vector, "payload": payload} for vector, payload in zip(vectors, payloads, strict=True)
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
                "score": 1.0,
            }
            for payload in payloads
        ]

    def delete_by_knowledge_id(self, knowledge_id: str) -> None:
        self.points = [item for item in self.points if item["payload"]["knowledge_id"] != knowledge_id]
        self.results = [item for item in self.results if item["knowledge_id"] != knowledge_id]

    def move_knowledge_to_kb(self, *, knowledge_id: str, target_kb_id: str) -> None:
        for item in self.points:
            if item["payload"].get("knowledge_id") == knowledge_id:
                item["payload"]["knowledge_base_id"] = target_kb_id
        for item in self.results:
            if item.get("knowledge_id") == knowledge_id:
                item["knowledge_base_id"] = target_kb_id

    def search(
        self,
        *,
        knowledge_base_id: str,
        query_vector: list[float],
        limit: int,
        score_threshold: float | None = None,
    ) -> list[dict]:
        results = [
            item
            for item in self.results
            if item["knowledge_base_id"] == knowledge_base_id
        ]
        if score_threshold is not None:
            results = [item for item in results if float(item.get("score") or 0) >= score_threshold]
        return results[:limit]


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def fake_chat_model() -> FakeChatModel:
    return FakeChatModel()


@pytest.fixture
def fake_vector_store() -> FakeVectorStore:
    return FakeVectorStore()


@pytest.fixture
def db_session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(
    db_session: Session,
    fake_embedder: FakeEmbedder,
    fake_chat_model: FakeChatModel,
    fake_vector_store: FakeVectorStore,
    tmp_path: Path,
) -> Iterator[TestClient]:
    app = create_app(
        settings=Settings(
            database_url="sqlite://",
            upload_dir=tmp_path,
            celery_broker_url="memory://",
            celery_result_backend="cache+memory://",
            model_config_encryption_key=Fernet.generate_key().decode("ascii"),
        ),
        session_factory=lambda: db_session,
        embedder=fake_embedder,
        chat_model=fake_chat_model,
        vector_store=fake_vector_store,
    )
    with TestClient(app) as test_client:
        yield test_client


def create_bound_models(client: TestClient) -> tuple[str, str]:
    chat_response = client.post(
        "/api/v1/models",
        json={
            "name": "Test Chat",
            "type": "KnowledgeQA",
            "provider": "qwen",
            "source": "remote",
            "base_url": "https://example.com/v1",
            "api_key": "sk-test-1234",
            "model_name": "qwen-plus",
        },
    )
    assert chat_response.status_code == 201, chat_response.text
    embedding_response = client.post(
        "/api/v1/models",
        json={
            "name": "Test Embedding",
            "type": "Embedding",
            "provider": "qwen",
            "source": "remote",
            "base_url": "https://example.com/v1",
            "api_key": "sk-test-1234",
            "model_name": "text-embedding-v4",
            "embedding_dimension": 3,
        },
    )
    assert embedding_response.status_code == 201, embedding_response.text
    return chat_response.json()["id"], embedding_response.json()["id"]
