from collections.abc import Iterator
from pathlib import Path

import pytest
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
                "score": 1.0,
            }
            for payload in payloads
        ]

    def search(self, *, knowledge_base_id: str, query_vector: list[float], limit: int) -> list[dict]:
        return [
            item
            for item in self.results
            if item["knowledge_base_id"] == knowledge_base_id
        ][:limit]


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
        ),
        session_factory=lambda: db_session,
        embedder=fake_embedder,
        chat_model=fake_chat_model,
        vector_store=fake_vector_store,
    )
    with TestClient(app) as test_client:
        yield test_client
