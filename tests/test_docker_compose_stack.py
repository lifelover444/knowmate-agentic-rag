from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_docker_compose_defines_api_and_worker_services():
    compose = read("docker-compose.yml")

    assert "  api:" in compose
    assert "  worker:" in compose
    assert "build:" in compose
    assert "dockerfile: Dockerfile" in compose
    assert "uvicorn app.main:app" in compose
    assert "celery -A app.workers.celery_app:celery_app worker" in compose
    assert "alembic upgrade head" in compose
    assert "DATABASE_URL=postgresql+psycopg://knowmate:knowmate@postgres:5432/knowmate" in compose
    assert "CELERY_BROKER_URL=redis://redis:6379/0" in compose
    assert "CELERY_RESULT_BACKEND=redis://redis:6379/1" in compose
    assert "QDRANT_HOST=qdrant" in compose
    assert "depends_on:" in compose
    assert "condition: service_healthy" in compose


def test_dockerfile_installs_project_and_runtime_dependencies():
    dockerfile = read("Dockerfile")

    assert "FROM python:3.11-slim" in dockerfile
    assert "pip install" in dockerfile
    assert ".[dev]" in dockerfile
    assert "WORKDIR /app" in dockerfile
    assert "EXPOSE 8000" in dockerfile


def test_dockerignore_keeps_runtime_artifacts_out_of_image():
    dockerignore = read(".dockerignore")

    assert ".runtime-logs/" in dockerignore
    assert "frontend/dist/" in dockerignore
    assert "storage/uploads/" in dockerignore
    assert ".env" in dockerignore
