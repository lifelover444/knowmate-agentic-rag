from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.models import Base, ModelConfig
from app.main import create_app


class FakeModelTester:
    def __init__(self, *, embedding_dimension: int | None = None) -> None:
        self.embedding_dimension = embedding_dimension

    def test(self, config):
        detected_dimension = self.embedding_dimension or config.embedding_dimension
        return {
            "chat_ok": True,
            "embedding_ok": detected_dimension == config.embedding_dimension,
            "detected_dimension": detected_dimension,
            "message": "连接测试通过" if detected_dimension == config.embedding_dimension else "向量维度不匹配",
        }


class FakeVectorStore:
    pass


@pytest.fixture
def model_client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite:///{tmp_path / 'model-config.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    settings = Settings(
        database_url="sqlite://",
        upload_dir=tmp_path,
        celery_broker_url="memory://",
        celery_result_backend="cache+memory://",
        model_config_encryption_key=Fernet.generate_key().decode("ascii"),
    )
    app = create_app(
        settings=settings,
        session_factory=SessionLocal,
        model_tester=FakeModelTester(),
        vector_store=FakeVectorStore(),
    )
    with TestClient(app) as client:
        yield client


def test_model_config_save_encrypts_api_key_and_never_returns_plaintext(model_client: TestClient):
    response = model_client.put(
        "/api/v1/model-config",
        json={
            "provider": "qwen",
            "name": "Qwen 百炼",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "sk-real-secret-1234",
            "chat_model": "qwen-plus",
            "embedding_model": "text-embedding-v4",
            "embedding_dimension": 1024,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_key_configured"] is True
    assert payload["api_key_last4"] == "1234"
    assert "sk-real-secret-1234" not in response.text

    with model_client.app.state.session_factory() as session:
        row = session.query(ModelConfig).one()
        assert row.api_key_encrypted != "sk-real-secret-1234"
        assert row.api_key_last4 == "1234"

    get_response = model_client.get("/api/v1/model-config")
    assert get_response.status_code == 200
    assert "sk-real-secret-1234" not in get_response.text
    assert get_response.json()["api_key_configured"] is True


def test_model_config_requires_api_key_on_first_save(model_client: TestClient):
    response = model_client.put(
        "/api/v1/model-config",
        json={
            "provider": "openai-compatible",
            "name": "Custom",
            "base_url": "https://example.com/v1",
            "chat_model": "chat-model",
            "embedding_model": "embedding-model",
            "embedding_dimension": 1536,
        },
    )

    assert response.status_code == 400
    assert "API Key" in response.text


def test_model_config_test_reports_dimension_mismatch(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mismatch.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    app = create_app(
        settings=Settings(
            database_url="sqlite://",
            upload_dir=tmp_path,
            model_config_encryption_key=Fernet.generate_key().decode("ascii"),
        ),
        session_factory=SessionLocal,
        model_tester=FakeModelTester(embedding_dimension=512),
        vector_store=FakeVectorStore(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/model-config/test",
            json={
                "provider": "qwen",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api_key": "sk-test",
                "chat_model": "qwen-plus",
                "embedding_model": "text-embedding-v4",
                "embedding_dimension": 1024,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["chat_ok"] is True
    assert payload["embedding_ok"] is False
    assert payload["detected_dimension"] == 512
