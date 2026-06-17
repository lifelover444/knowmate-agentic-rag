from conftest import configure_rerank, create_bound_models
from fastapi.testclient import TestClient

from app.db.models import Chunk, Knowledge

LEGAL_QUERY = (
    "张某驾驶汽车正常行驶时突发心脏病昏迷，车辆失控撞伤路边行人李某。"
    "经鉴定，张某在驾驶前并不知道自己患有严重心脏疾病，也不存在酒驾、疲劳驾驶等违法行为。"
    "张某是否需要承担侵权责任？李某的医疗费、误工费等损失由谁承担？"
    "如果张某购买了交强险和商业三者险，赔偿顺序是什么？"
    "如果张某因昏迷已经死亡，李某还能向谁主张赔偿？"
)

TARGET_TERMS = ("机动车", "交通事故", "交强险", "商业三者险", "医疗费", "误工费")
HARD_TARGET_TERMS = ("机动车", "交通事故", "交强险", "商业三者险")
DISTRACTOR_TERMS = ("饲养动物", "高度危险动物", "动物致害")


class LegalAwareReranker:
    def rerank(self, *, query: str, documents: list[str], top_n: int):
        scored = []
        for index, document in enumerate(documents):
            hard_hits = sum(1 for term in HARD_TARGET_TERMS if term in document)
            target_hits = sum(1 for term in TARGET_TERMS if term in document)
            distractor_hits = sum(1 for term in DISTRACTOR_TERMS if term in document)
            score = 0.2 + hard_hits * 0.16 + target_hits * 0.03 - distractor_hits * 0.12
            score = max(0.05, min(score, 0.99))
            scored.append((index, score))
        return scored[:top_n]


def _create_kb(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "TASK-056 法律召回夹具", "embedding_model_id": embedding_id, "summary_model_id": chat_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _add_legal_fixture_document(db_session, kb_id: str) -> None:
    document_id = "doc-task056-civil-code"
    db_session.add(
        Knowledge(
            id=document_id,
            tenant_id=10000,
            knowledge_base_id=kb_id,
            type="file",
            title="中华人民共和国民法典_20200528.pdf",
            source="upload",
            parse_status="completed",
            enable_status="enabled",
            file_size=0,
            storage_size=0,
        )
    )
    chunks = [
        Chunk(
            id="task056-parent-animal",
            tenant_id=10000,
            knowledge_base_id=kb_id,
            knowledge_id=document_id,
            content=(
                "第一千二百四十七条 禁止饲养的烈性犬等危险动物造成他人损害的，"
                "动物饲养人或者管理人应当承担侵权责任。受害人主张医疗费、误工费等损失时，"
                "应结合侵权责任编的一般赔偿规则处理。"
            ),
            search_text="民法典 侵权责任 饲养动物 高度危险动物 医疗费 误工费 赔偿责任",
            chunk_index=0,
            start_at=0,
            end_at=88,
            chunk_type="parent",
            context_header="# 侵权责任编 / 饲养动物损害责任",
            chunk_metadata={"source_type": "document", "title": "中华人民共和国民法典_20200528.pdf"},
        ),
        Chunk(
            id="task056-child-animal",
            tenant_id=10000,
            knowledge_base_id=kb_id,
            knowledge_id=document_id,
            content=(
                "饲养动物损害责任：禁止饲养的烈性犬等高度危险动物造成他人损害的，"
                "动物饲养人或者管理人承担侵权责任。相关损失可包括医疗费、误工费。"
            ),
            search_text="张某 李某 侵权责任 医疗费 误工费 赔偿 饲养动物 高度危险动物 动物致害",
            chunk_index=1,
            start_at=0,
            end_at=66,
            chunk_type="child",
            parent_chunk_id="task056-parent-animal",
            context_header="# 侵权责任编 / 饲养动物损害责任",
            chunk_metadata={"source_type": "document", "title": "中华人民共和国民法典_20200528.pdf"},
        ),
        Chunk(
            id="task056-parent-traffic",
            tenant_id=10000,
            knowledge_base_id=kb_id,
            knowledge_id=document_id,
            content=(
                "机动车发生交通事故造成损害，属于该机动车一方责任的，先由承保机动车强制保险的"
                "保险人在交强险责任限额范围内予以赔偿；不足部分，由承保商业三者险的保险人按照"
                "保险合同约定赔偿；仍然不足的，由侵权人赔偿。医疗费、误工费、死亡赔偿等依法处理。"
            ),
            search_text="民法典 机动车 交通事故 交强险 商业三者险 医疗费 误工费 死亡赔偿 侵权责任",
            chunk_index=2,
            start_at=100,
            end_at=235,
            chunk_type="parent",
            context_header="# 侵权责任编 / 机动车交通事故责任",
            chunk_metadata={"source_type": "document", "title": "中华人民共和国民法典_20200528.pdf"},
        ),
        Chunk(
            id="task056-child-traffic",
            tenant_id=10000,
            knowledge_base_id=kb_id,
            knowledge_id=document_id,
            content=(
                "机动车交通事故责任：交强险先行赔偿，不足部分由商业三者险按合同赔偿；"
                "仍不足的，由侵权人承担。医疗费、误工费、死亡赔偿等损失按责任和保险顺序处理。"
            ),
            search_text=(
                "张某 李某 机动车 交通事故 交强险 商业三者险 医疗费 误工费 "
                "死亡赔偿 侵权责任 赔偿顺序"
            ),
            chunk_index=3,
            start_at=100,
            end_at=178,
            chunk_type="child",
            parent_chunk_id="task056-parent-traffic",
            context_header="# 侵权责任编 / 机动车交通事故责任",
            chunk_metadata={"source_type": "document", "title": "中华人民共和国民法典_20200528.pdf"},
        ),
    ]
    db_session.add_all(chunks)
    db_session.commit()


def _run_fixture(client: TestClient, db_session, fake_vector_store, monkeypatch) -> tuple[dict, dict]:
    kb_id = _create_kb(client)
    configure_rerank(client)
    _add_legal_fixture_document(db_session, kb_id)
    monkeypatch.setattr("app.services.knowledge_search.RerankerClient", lambda _config: LegalAwareReranker())
    fake_vector_store.results = [
        {
            "chunk_id": "task056-child-animal",
            "knowledge_id": "doc-task056-civil-code",
            "knowledge_base_id": kb_id,
            "content": "饲养动物损害责任：高度危险动物造成他人损害的，饲养人承担侵权责任。",
            "title": "中华人民共和国民法典_20200528.pdf",
            "score": 0.91,
            "chunk_type": "child",
            "parent_chunk_id": "task056-parent-animal",
            "context_header": "# 侵权责任编 / 饲养动物损害责任",
            "metadata": {"source_type": "document", "title": "中华人民共和国民法典_20200528.pdf"},
        },
        {
            "chunk_id": "task056-child-traffic",
            "knowledge_id": "doc-task056-civil-code",
            "knowledge_base_id": kb_id,
            "content": "机动车交通事故责任：交强险先行赔偿，不足部分由商业三者险按合同赔偿。",
            "title": "中华人民共和国民法典_20200528.pdf",
            "score": 0.87,
            "chunk_type": "child",
            "parent_chunk_id": "task056-parent-traffic",
            "context_header": "# 侵权责任编 / 机动车交通事故责任",
            "metadata": {"source_type": "document", "title": "中华人民共和国民法典_20200528.pdf"},
        },
    ]

    response = client.post(
        "/api/v1/quick-answer",
        json={"knowledge_base_id": kb_id, "query": LEGAL_QUERY, "top_k": 1},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    trace = payload["retrieval_trace"]
    stages = {stage["name"]: stage for stage in trace["stages"]}
    selected_text = "\n".join(item.get("snippet") or "" for item in trace["selected_contexts"])
    report = {
        "query": LEGAL_QUERY,
        "vector_candidates": [item["chunk_id"] for item in fake_vector_store.results],
        "stage_counts": {
            "vector": stages["vector"]["output"]["hit_count"],
            "keyword": stages["keyword"]["output"]["hit_count"],
            "rrf": stages["rrf"]["output"]["output_count"],
            "rerank_input": stages["rerank"]["output"]["rerank_input_count"],
            "rerank_output": stages["rerank"]["output"]["rerank_output_count"],
            "selected_contexts": stages["context_select"]["output"]["selected_context_count"],
        },
        "selected_contexts": trace["selected_contexts"],
        "selected_has_target_terms": any(term in selected_text for term in HARD_TARGET_TERMS),
        "selected_has_distractor_terms": any(term in selected_text for term in DISTRACTOR_TERMS),
        "expected_terms": list(TARGET_TERMS),
        "distractor_terms": list(DISTRACTOR_TERMS),
    }
    return payload, report


def test_task056_legal_retrieval_fixture_exposes_trace_and_candidates(
    client,
    db_session,
    fake_vector_store,
    monkeypatch,
):
    payload, report = _run_fixture(client, db_session, fake_vector_store, monkeypatch)
    trace = payload["retrieval_trace"]
    stage_names = [stage["name"] for stage in trace["stages"]]

    assert trace["query_original"] == LEGAL_QUERY
    assert report["vector_candidates"] == ["task056-child-animal", "task056-child-traffic"]
    assert "task056-child-traffic" in report["vector_candidates"]
    assert {"vector", "keyword", "rrf", "deduplicate", "rerank", "parent_expand", "context_select", "answer"}.issubset(
        stage_names
    )
    assert report["stage_counts"]["vector"] == 2
    assert report["stage_counts"]["keyword"] >= 1
    assert report["stage_counts"]["rrf"] >= 2
    assert report["stage_counts"]["rerank_input"] >= 2
    assert report["stage_counts"]["selected_contexts"] >= 1
    assert trace["selected_contexts"]
    assert payload["sources"]
    assert any(term in LEGAL_QUERY for term in report["expected_terms"])

def test_task063_legal_fixture_ranks_traffic_context_before_animal_context(
    client,
    db_session,
    fake_vector_store,
    monkeypatch,
):
    _payload, report = _run_fixture(client, db_session, fake_vector_store, monkeypatch)

    assert report["selected_has_target_terms"] is True
    assert report["selected_has_distractor_terms"] is False
