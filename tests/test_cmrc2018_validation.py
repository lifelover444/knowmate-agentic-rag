import json
from pathlib import Path

import pytest

from app.services import cmrc2018_validation as cmrc


def _official_style_payload(context_count: int = 220) -> dict:
    data = []
    for index in range(context_count):
        answer = f"答案{index}"
        context = f"这是第{index}篇互不相同的中文语料。该语料的明确事实是{answer}，用于测试稳定映射。"
        data.append(
            {
                "id": f"DEV_ARTICLE_{index}",
                "title": f"标题{index}",
                "paragraphs": [
                    {
                        "id": f"DEV_{index}",
                        "context": context,
                        "qas": [
                            {
                                "id": f"DEV_{index}_QUERY_0",
                                "question": f"第{index}篇语料的明确事实是什么？",
                                "answers": [{"text": answer, "answer_start": context.index(answer)}],
                            }
                        ],
                    }
                ],
            }
        )
    return {"version": "v1.0", "data": data}


def _prepare_fixture(tmp_path: Path, monkeypatch) -> Path:
    source = json.dumps(_official_style_payload(), ensure_ascii=False).encode()

    def fake_download(url: str, _expected_hash: str) -> bytes:
        return b"CC BY-SA 4.0 fixture" if url == cmrc.CMRC2018_LICENSE_URL else source

    monkeypatch.setattr(cmrc, "_download_verified", fake_download)
    output = tmp_path / "cmrc"
    cmrc.prepare_cmrc2018_dataset(output)
    return output


def test_prepare_cmrc_dataset_is_reproducible_and_corpus_contains_only_context(tmp_path, monkeypatch):
    first = _prepare_fixture(tmp_path / "first", monkeypatch)
    second = _prepare_fixture(tmp_path / "second", monkeypatch)
    first_manifest = json.loads((first / "corpus_manifest.json").read_text(encoding="utf-8"))
    second_manifest = json.loads((second / "corpus_manifest.json").read_text(encoding="utf-8"))
    gold = json.loads((first / "golden_questions.raw.json").read_text(encoding="utf-8"))

    assert first_manifest == second_manifest
    assert first_manifest["counts"] == {
        "contexts": 200,
        "target_contexts": 20,
        "distractor_contexts": 180,
    }
    assert len({item["dataset_context_id"] for item in first_manifest["contexts"]}) == 200
    assert len({item["dataset_context_id"] for item in gold["questions"]}) == 20
    assert {item["dataset_context_id"] for item in gold["questions"]} == {
        item["dataset_context_id"] for item in first_manifest["contexts"] if item["role"] == "target"
    }

    source_contexts = {
        paragraph["id"]: paragraph["context"]
        for article in _official_style_payload()["data"]
        for paragraph in article["paragraphs"]
    }
    for item in first_manifest["contexts"]:
        uploaded_text = (first / "corpus" / item["document_filename"]).read_text(encoding="utf-8")
        assert uploaded_text == source_contexts[item["source_context_id"]]


def test_select_answer_chunk_ignores_parent_and_uses_source_offset():
    chunks = [
        {
            "id": "parent",
            "content": "前文 目标答案 后文",
            "start_at": 0,
            "chunk_index": 0,
            "chunk_type": "parent",
            "is_enabled": True,
        },
        {
            "id": "wrong-occurrence",
            "content": "目标答案 在错误位置",
            "start_at": 0,
            "chunk_index": 1,
            "chunk_type": "child",
            "is_enabled": True,
        },
        {
            "id": "expected-child",
            "content": "目标答案 在正确位置",
            "start_at": 100,
            "chunk_index": 2,
            "chunk_type": "child",
            "is_enabled": True,
        },
    ]

    selected = cmrc.select_answer_chunk(chunks, [{"text": "目标答案", "answer_start": 100}])

    assert selected["chunk_id"] == "expected-child"
    assert selected["chunk_type"] == "child"


def test_bind_maps_stable_context_ids_to_real_answer_chunks_and_import_payload(tmp_path, monkeypatch):
    output = _prepare_fixture(tmp_path, monkeypatch)
    corpus = json.loads((output / "corpus_manifest.json").read_text(encoding="utf-8"))
    gold = json.loads((output / "golden_questions.raw.json").read_text(encoding="utf-8"))
    questions_by_filename = {item["document_filename"]: item for item in gold["questions"]}

    class FakeAPI:
        imported = None

        def list_documents(self, _knowledge_base_id: str) -> list[dict]:
            return [
                {
                    "id": f"doc-{item['source_context_id']}",
                    "file_name": item["document_filename"],
                    "parse_status": "completed",
                    "file_size": item["context_bytes"],
                    "chunk_count": 2,
                }
                for item in corpus["contexts"]
            ]

        def list_document_chunks(self, document_id: str) -> list[dict]:
            filename = next(
                item["document_filename"]
                for item in corpus["contexts"]
                if document_id == f"doc-{item['source_context_id']}"
            )
            question = questions_by_filename[filename]
            answer = question["answers"][0]
            return [
                {
                    "id": f"parent-{document_id}",
                    "content": answer["text"],
                    "start_at": answer["answer_start"],
                    "chunk_index": 0,
                    "chunk_type": "parent",
                    "is_enabled": True,
                },
                {
                    "id": f"child-{document_id}",
                    "content": answer["text"],
                    "start_at": answer["answer_start"],
                    "chunk_index": 1,
                    "chunk_type": "child",
                    "is_enabled": True,
                },
            ]

        def create_or_reuse_testset(self, payload: dict) -> dict:
            self.imported = payload
            return {"id": "testset-cmrc", **payload, "item_count": len(payload["items"])}

    api = FakeAPI()
    result = cmrc.bind_and_import_testset(
        api,
        dataset_dir=output,
        knowledge_base_id="kb-cmrc",
    )

    assert result["question_count"] == 20
    assert result["testset"]["id"] == "testset-cmrc"
    assert len(api.imported["items"]) == 20
    assert all(item["expected_chunk_ids"][0].startswith("child-doc-DEV_") for item in api.imported["items"])
    bindings = json.loads((output / "chunk_bindings.json").read_text(encoding="utf-8"))
    assert len({item["dataset_context_id"] for item in bindings["bindings"]}) == 20


def test_comparison_rejects_semantic_proxy_but_preserves_results(tmp_path):
    class FakeAPI:
        created = 0

        def create_evaluation(self, _payload: dict) -> dict:
            self.created += 1
            return {"id": f"run-{self.created}"}

        def get_evaluation(self, run_id: str) -> dict:
            rerank = run_id == "run-2"
            return {
                "id": run_id,
                "status": "completed",
                "top_k": 5,
                "enable_rerank": rerank,
                "evaluator_config": {"mode": "native_ragas" if rerank else "semantic_proxy"},
                "metrics_summary": {"overall_score": 0.5, "metrics": {}},
                "sample_count": 20,
                "completed_sample_count": 20,
                "failed_sample_count": 0,
                "samples": [],
                "error_message": None,
            }

    with pytest.raises(cmrc.CMRCValidationError, match="semantic_proxy"):
        cmrc.run_native_ragas_comparison(
            FakeAPI(),
            knowledge_base_id="kb",
            testset_id="testset",
            output_dir=tmp_path,
            poll_interval=0,
        )

    report = json.loads((tmp_path / "comparison.json").read_text(encoding="utf-8"))
    assert report["native_ragas_verified"] is False
    assert (tmp_path / "rerank_off.json").is_file()
    assert "semantic_proxy" in (tmp_path / "comparison.md").read_text(encoding="utf-8")
