from conftest import create_bound_models
from fastapi.testclient import TestClient


def test_quick_answer_stream_persists_user_mentioned_items(client: TestClient):
    chat_id, embedding_id = create_bound_models(client)
    kb = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "mention KB", "summary_model_id": chat_id, "embedding_model_id": embedding_id},
    ).json()
    mentioned_items = [{"id": kb["id"], "name": "mention KB", "type": "kb", "kb_type": "document"}]

    response = client.post(
        "/api/v1/quick-answer/stream",
        json={
            "knowledge_base_id": kb["id"],
            "knowledge_base_ids": [kb["id"]],
            "query": "提问",
            "mode": "keyword_only",
            "mentioned_items": mentioned_items,
        },
    )

    assert response.status_code == 200, response.text
    session_id = None
    for line in response.text.splitlines():
        if line.startswith("data: ") and '"assistant_message"' in line:
            break
        if line.startswith("data: ") and '"knowledge_base_id"' in line:
            import json

            session_id = json.loads(line.removeprefix("data: "))["id"]
    assert session_id

    detail = client.get(f"/api/v1/chat-sessions/{session_id}")
    assert detail.status_code == 200, detail.text
    user_message = next(item for item in detail.json()["messages"] if item["role"] == "user")
    assert user_message["mentioned_items"] == mentioned_items
