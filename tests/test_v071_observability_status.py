from conftest import create_bound_models
from fastapi.testclient import TestClient

from tests.test_v06_quick_answer_stream import FixedScoreReranker, configure_rerank, parse_sse_events


def create_kb(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "observability KB", "embedding_model_id": embedding_id, "summary_model_id": chat_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_quick_answer_stream_returns_stage_trace(client, fake_vector_store, monkeypatch):
    kb_id = create_kb(client)
    configure_rerank(client)
    monkeypatch.setattr("app.services.knowledge_search.RerankerClient", lambda _config: FixedScoreReranker())
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-trace-stage",
            "knowledge_id": "doc-trace-stage",
            "knowledge_base_id": kb_id,
            "content": "阶段化 trace 应展示检索和回答过程。",
            "title": "Trace 文档",
            "score": 0.91,
        }
    ]

    response = client.post(
        "/api/v1/quick-answer/stream",
        json={"knowledge_base_id": kb_id, "query": "trace 怎么看？", "mode": "vector_only", "top_k": 5},
    )

    assert response.status_code == 200, response.text
    trace = dict(parse_sse_events(response.text))["final"]["retrieval_trace"]
    stages = {stage["name"]: stage for stage in trace["stages"]}
    assert list(stages) == [
        "rewrite",
        "vector",
        "keyword",
        "rrf",
        "query_expansion",
        "deduplicate",
        "faq_merge",
        "rerank",
        "parent_expand",
        "context_select",
        "answer",
    ]
    assert stages["rewrite"]["status"] == "done"
    assert stages["rewrite"]["output"]["intent"] == "kb_search"
    assert stages["vector"]["status"] == "done"
    assert stages["vector"]["output"]["hit_count"] == 1
    assert stages["keyword"]["status"] == "done"
    assert stages["rrf"]["status"] == "done"
    assert stages["query_expansion"]["status"] in {"done", "skipped"}
    assert stages["deduplicate"]["status"] == "done"
    assert stages["faq_merge"]["status"] == "done"
    assert stages["faq_merge"]["output"]["boost_count"] == 0
    assert stages["rerank"]["status"] == "done"
    assert stages["parent_expand"]["status"] == "done"
    assert stages["context_select"]["status"] == "done"
    assert stages["answer"]["status"] == "done"
    assert all(isinstance(stage["duration_ms"], int) and stage["duration_ms"] >= 0 for stage in stages.values())


def test_runtime_status_reports_real_parser_storage_and_system_health(client):
    create_bound_models(client)
    response = client.get("/api/v1/runtime-status")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["system"]["status"] == "ok"
    assert payload["database"]["status"] == "ok"
    assert payload["storage"]["provider"] == "local"
    assert payload["storage"]["status"] == "ok"
    assert payload["storage"]["writable"] is True
    assert payload["vector_store"]["status"] == "ok"
    assert payload["model_configs"]["required_types"]["KnowledgeQA"]["status"] == "ok"
    assert payload["model_configs"]["required_types"]["Embedding"]["status"] == "ok"
    assert payload["model_configs"]["required_types"]["Rerank"]["status"] == "missing"
    assert payload["model_configs"]["summary"]["total"] == 2
    assert payload["model_configs"]["summary"]["api_key_configured"] == 2
    assert "sk-test" not in response.text
    assert payload["vector_stores"]["registered_count"] >= 1
    assert payload["vector_stores"]["default"]["provider"] == "qdrant"
    assert payload["vector_stores"]["default"]["config_json"]["api_key_configured"] is False
    assert any(
        provider["provider"] == "local" and provider["status"] == "ok"
        for provider in payload["storage_providers"]
    )
    assert any(
        provider["provider"] == "minio" and provider["status"] == "planned"
        for provider in payload["storage_providers"]
    )
    builtin = next(engine for engine in payload["parser_engines"] if engine["name"] == "builtin")
    mineru = next(engine for engine in payload["parser_engines"] if engine["name"] == "mineru")
    docreader = next(engine for engine in payload["parser_engines"] if engine["name"] == "docreader")
    assert builtin["status"] == "ok"
    assert "pdf" in builtin["file_types"]
    assert mineru["status"] == "planned"
    assert docreader["status"] == "planned"
    assert any("Rerank" in suggestion for suggestion in payload["fix_suggestions"])
