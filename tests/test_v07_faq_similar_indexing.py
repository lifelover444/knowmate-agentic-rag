from io import BytesIO

from conftest import FixedScoreReranker, configure_rerank, create_bound_models
from fastapi.testclient import TestClient

from app.db.models import Chunk, FAQEntry


def _create_faq_kb(client: TestClient, faq_config: dict | None = None) -> str:
    chat_id, embedding_id = create_bound_models(client)
    payload = {
        "name": "FAQ similar KB",
        "kb_type": "faq",
        "summary_model_id": chat_id,
        "embedding_model_id": embedding_id,
    }
    if faq_config:
        payload["faq_config"] = faq_config
    response = client.post("/api/v1/knowledge-bases", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["faq_config"]["index_mode"]
    assert data["faq_config"]["question_index_mode"]
    return data["id"]


def test_faq_similar_questions_are_deduped_and_import_exported(client: TestClient, db_session):
    kb_id = _create_faq_kb(client)

    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/faqs",
        json={
            "question": "如何修改密码？",
            "similar_questions": ["怎么改密码", "怎么改密码", "  ", "忘记密码怎么办"],
            "answer": "进入设置中心修改密码。",
            "enabled": True,
        },
    )

    assert response.status_code == 201, response.text
    faq = response.json()
    assert faq["similar_questions"] == ["怎么改密码", "忘记密码怎么办"]
    entry = db_session.get(FAQEntry, faq["id"])
    assert entry.similar_questions == ["怎么改密码", "忘记密码怎么办"]

    export_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/faqs/export?format=csv")
    assert export_response.status_code == 200, export_response.text
    csv_text = export_response.content.decode("utf-8-sig")
    assert "similar_questions" in csv_text
    assert "怎么改密码##忘记密码怎么办" in csv_text

    csv_data = (
        "question,similar_questions,answer,metadata,enabled,tag_id\n"
        "如何绑定手机,绑定手机号##更换手机号,进入账号安全绑定手机,{},true,\n"
    )
    import_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/faqs/import",
        data={"mode": "append"},
        files={"file": ("faqs.csv", BytesIO(csv_data.encode("utf-8")), "text/csv")},
    )
    assert import_response.status_code == 200, import_response.text
    imported = client.get(f"/api/v1/knowledge-bases/{kb_id}/faqs").json()
    imported_item = next(item for item in imported if item["question"] == "如何绑定手机")
    assert imported_item["similar_questions"] == ["绑定手机号", "更换手机号"]


def test_faq_index_modes_control_question_answer_and_separate_chunks(
    client: TestClient,
    db_session,
    fake_vector_store,
    monkeypatch,
):
    configure_rerank(client)
    monkeypatch.setattr("app.services.knowledge_search.RerankerClient", lambda _config: FixedScoreReranker())
    question_only_kb = _create_faq_kb(
        client,
        {"index_mode": "question_only", "question_index_mode": "combined"},
    )
    first = client.post(
        f"/api/v1/knowledge-bases/{question_only_kb}/faqs",
        json={
            "question": "如何修改密码？",
            "similar_questions": ["怎么改密码"],
            "answer": "进入设置中心修改密码。",
            "enabled": True,
        },
    ).json()
    chunks = db_session.query(Chunk).filter_by(knowledge_id=first["knowledge_id"]).all()
    assert len(chunks) == 1
    assert "怎么改密码" in chunks[0].search_text
    assert "进入设置中心修改密码" not in chunks[0].search_text

    separate_kb = _create_faq_kb(
        client,
        {"index_mode": "question_answer", "question_index_mode": "separate"},
    )
    second_response = client.post(
        f"/api/v1/knowledge-bases/{separate_kb}/faqs",
        json={
            "question": "如何开票？",
            "similar_questions": ["发票怎么申请", "哪里下载发票"],
            "answer": "在订单中心申请发票。",
            "enabled": True,
        },
    )
    assert second_response.status_code == 201, second_response.text
    second = second_response.json()
    chunks = db_session.query(Chunk).filter_by(knowledge_id=second["knowledge_id"]).order_by(Chunk.chunk_index).all()
    assert len(chunks) == 3
    assert [chunk.chunk_metadata["matched_question"] for chunk in chunks] == [
        "如何开票？",
        "发票怎么申请",
        "哪里下载发票",
    ]
    assert all("在订单中心申请发票" in chunk.search_text for chunk in chunks)

    search_response = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": separate_kb, "query": "发票怎么申请", "mode": "keyword_only"},
    )
    assert search_response.status_code == 200, search_response.text
    assert any(hit["metadata"]["matched_question"] == "发票怎么申请" for hit in search_response.json()["hits"])
    assert any(point["payload"]["metadata"]["matched_question"] == "哪里下载发票" for point in fake_vector_store.points)
