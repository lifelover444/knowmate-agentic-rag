from __future__ import annotations

import hashlib
import json
import random
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

CMRC2018_COMMIT = "c0eb1b6ba219847457e6af3180da722bbeb656af"
CMRC2018_DEV_URL = (
    "https://raw.githubusercontent.com/ymcui/cmrc2018/"
    f"{CMRC2018_COMMIT}/squad-style-data/cmrc2018_dev.json"
)
CMRC2018_DEV_SHA256 = "e9ff74231f05c230c6fa88b84441ee334d97234cbb610991cd94b82db00c7f1f"
CMRC2018_LICENSE_URL = (
    "https://raw.githubusercontent.com/ymcui/cmrc2018/"
    f"{CMRC2018_COMMIT}/LICENCE"
)
CMRC2018_LICENSE_SHA256 = "7abe19ec9bb73b36141b999b861d24ad855e808bafe0f81e84cce28556f6c297"
DEFAULT_SEED = 20240722
DEFAULT_TARGET_COUNT = 20
DEFAULT_DISTRACTOR_COUNT = 180
TERMINAL_DOCUMENT_STATUSES = {"completed", "failed", "cancelled"}
TERMINAL_EVALUATION_STATUSES = {"completed", "failed"}


class CMRCValidationError(RuntimeError):
    pass


def prepare_cmrc2018_dataset(
    output_dir: str | Path,
    *,
    seed: int = DEFAULT_SEED,
    target_count: int = DEFAULT_TARGET_COUNT,
    distractor_count: int = DEFAULT_DISTRACTOR_COUNT,
    source_path: str | Path | None = None,
    force: bool = False,
) -> dict:
    root = Path(output_dir)
    corpus_dir = root / "corpus"
    source_dir = root / "source"
    manifest_path = root / "corpus_manifest.json"
    gold_path = root / "golden_questions.raw.json"
    generated_paths = [manifest_path, gold_path, root / "SOURCE_AND_LICENSE.md"]
    existing_corpus = list(corpus_dir.glob("cmrc2018_validation__*.txt")) if corpus_dir.exists() else []
    if not force and (existing_corpus or any(path.exists() for path in generated_paths)):
        raise CMRCValidationError(f"输出目录已有 CMRC2018 产物：{root}；如需重建请传 --force。")

    source_dir.mkdir(parents=True, exist_ok=True)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    if force:
        for path in existing_corpus:
            path.unlink()

    if source_path is None:
        source_bytes = _download_verified(CMRC2018_DEV_URL, CMRC2018_DEV_SHA256)
        raw_source_path = source_dir / "cmrc2018_dev.json"
        raw_source_path.write_bytes(source_bytes)
    else:
        raw_source_path = Path(source_path)
        source_bytes = raw_source_path.read_bytes()
        actual_hash = _sha256(source_bytes)
        if actual_hash != CMRC2018_DEV_SHA256:
            raise CMRCValidationError(
                "指定的数据文件不是锁定的 CMRC2018 官方 dev 文件："
                f"期望 SHA-256={CMRC2018_DEV_SHA256}，实际={actual_hash}。"
            )
        copied_source_path = source_dir / "cmrc2018_dev.json"
        if raw_source_path.resolve() != copied_source_path.resolve():
            copied_source_path.write_bytes(source_bytes)
        raw_source_path = copied_source_path

    license_bytes = _download_verified(CMRC2018_LICENSE_URL, CMRC2018_LICENSE_SHA256)
    (source_dir / "CMRC2018_LICENCE.txt").write_bytes(license_bytes)

    try:
        source_payload = json.loads(source_bytes)
    except json.JSONDecodeError as exc:
        raise CMRCValidationError(f"CMRC2018 dev JSON 无法解析：{exc}") from exc
    records = _cmrc_context_records(source_payload)
    selected_targets, selected_distractors = _select_records(
        records,
        seed=seed,
        target_count=target_count,
        distractor_count=distractor_count,
    )
    target_ids = {record["source_context_id"] for record in selected_targets}
    selected_records = sorted(selected_targets + selected_distractors, key=lambda item: item["source_context_id"])

    contexts_manifest: list[dict] = []
    record_by_id = {record["source_context_id"]: record for record in selected_records}
    for record in selected_records:
        filename = _document_filename(record["source_context_id"])
        context_bytes = record["context"].encode("utf-8")
        (corpus_dir / filename).write_bytes(context_bytes)
        contexts_manifest.append(
            {
                "dataset_context_id": _dataset_context_id(record["source_context_id"]),
                "source_context_id": record["source_context_id"],
                "source_article_id": record["source_article_id"],
                "source_title": record["source_title"],
                "document_filename": filename,
                "role": "target" if record["source_context_id"] in target_ids else "distractor",
                "context_sha256": _sha256(context_bytes),
                "context_chars": len(record["context"]),
                "context_bytes": len(context_bytes),
            }
        )

    rng = random.Random(seed ^ 0xC0DE2018)
    questions: list[dict] = []
    for sample_index, record in enumerate(selected_targets):
        qa = rng.choice(record["valid_qas"])
        answers = _deduplicate_answers(qa["valid_answers"])
        reference_answer = answers[0]["text"]
        questions.append(
            {
                "sample_index": sample_index,
                "dataset_context_id": _dataset_context_id(record["source_context_id"]),
                "source_context_id": record["source_context_id"],
                "source_question_id": qa["id"],
                "question": qa["question"],
                "reference_answer": reference_answer,
                "answers": answers,
                "document_filename": _document_filename(record["source_context_id"]),
                "context_sha256": _sha256(record["context"].encode("utf-8")),
            }
        )

    manifest = {
        "schema_version": 1,
        "dataset": "CMRC2018",
        "dataset_id": "cmrc2018:validation",
        "split": "validation",
        "official_split_name": "dev",
        "seed": seed,
        "source": _source_metadata(),
        "counts": {
            "contexts": len(contexts_manifest),
            "target_contexts": len(selected_targets),
            "distractor_contexts": len(selected_distractors),
        },
        "contexts": contexts_manifest,
    }
    gold_manifest = {
        "schema_version": 1,
        "dataset": "CMRC2018",
        "dataset_id": "cmrc2018:validation",
        "split": "validation",
        "official_split_name": "dev",
        "seed": seed,
        "source": _source_metadata(),
        "question_count": len(questions),
        "questions": questions,
    }
    _write_json(manifest_path, manifest)
    _write_json(gold_path, gold_manifest)
    (root / "SOURCE_AND_LICENSE.md").write_text(_source_and_license_text(), encoding="utf-8")

    _validate_prepared_dataset(root, record_by_id)
    return {
        "output_dir": str(root),
        "source_path": str(raw_source_path),
        "corpus_manifest": str(manifest_path),
        "golden_manifest": str(gold_path),
        "counts": manifest["counts"] | {"questions": len(questions)},
        "seed": seed,
    }


def upload_and_wait_for_corpus(
    api: KnowMateAPI,
    *,
    dataset_dir: str | Path,
    knowledge_base_id: str,
    wait: bool = True,
    poll_interval: float = 5.0,
    timeout: float = 3600.0,
) -> dict:
    root = Path(dataset_dir)
    manifest = _read_json(root / "corpus_manifest.json")
    contexts = manifest.get("contexts") or []
    if len(contexts) != int((manifest.get("counts") or {}).get("contexts") or 0):
        raise CMRCValidationError("corpus_manifest.json 的 contexts 数量不一致。")
    documents = api.list_documents(knowledge_base_id)
    existing_by_filename = _documents_by_filename(documents)
    mappings: list[dict] = []
    uploaded_count = 0
    reused_count = 0

    for context in contexts:
        filename = str(context["document_filename"])
        path = root / "corpus" / filename
        _verify_context_file(path, context)
        document = existing_by_filename.get(filename)
        if document is None:
            document = api.upload_document(knowledge_base_id, path)
            existing_by_filename[filename] = document
            uploaded_count += 1
        else:
            expected_size = int(context["context_bytes"])
            if int(document.get("file_size") or -1) != expected_size:
                raise CMRCValidationError(
                    f"知识库中同名文件 {filename} 的大小与 manifest 不一致，拒绝错误复用。"
                )
            reused_count += 1
        mappings.append(_document_mapping(context, document))

    if wait:
        documents = _wait_for_documents(
            api,
            knowledge_base_id=knowledge_base_id,
            document_ids={row["document_id"] for row in mappings},
            poll_interval=poll_interval,
            timeout=timeout,
        )
        by_id = {str(document["id"]): document for document in documents}
        mappings = [
            _document_mapping(context, by_id[mapping["document_id"]])
            for context, mapping in zip(contexts, mappings, strict=True)
        ]

    state = {
        "schema_version": 1,
        "dataset_id": manifest["dataset_id"],
        "knowledge_base_id": knowledge_base_id,
        "updated_at": datetime.now(UTC).isoformat(),
        "uploaded_count": uploaded_count,
        "reused_count": reused_count,
        "waited_for_processing": wait,
        "documents": mappings,
    }
    _write_json(root / "upload_state.json", state)
    return state


def bind_and_import_testset(
    api: KnowMateAPI,
    *,
    dataset_dir: str | Path,
    knowledge_base_id: str,
    testset_name: str | None = None,
    import_testset: bool = True,
) -> dict:
    root = Path(dataset_dir)
    corpus_manifest = _read_json(root / "corpus_manifest.json")
    gold_manifest = _read_json(root / "golden_questions.raw.json")
    contexts_by_id = {
        str(item["dataset_context_id"]): item for item in (corpus_manifest.get("contexts") or [])
    }
    documents_by_filename = _documents_by_filename(api.list_documents(knowledge_base_id))
    bindings: list[dict] = []
    items: list[dict] = []

    for question in gold_manifest.get("questions") or []:
        dataset_context_id = str(question["dataset_context_id"])
        context = contexts_by_id.get(dataset_context_id)
        if context is None:
            raise CMRCValidationError(f"黄金题引用了 corpus manifest 中不存在的 context：{dataset_context_id}")
        filename = str(context["document_filename"])
        document = documents_by_filename.get(filename)
        if document is None:
            raise CMRCValidationError(f"知识库缺少目标 context 文档：{filename}")
        if document.get("parse_status") != "completed":
            raise CMRCValidationError(
                f"目标文档尚未成功解析：{filename}，parse_status={document.get('parse_status')}"
            )
        chunks = api.list_document_chunks(str(document["id"]))
        selected = select_answer_chunk(chunks, question.get("answers") or [])
        binding = {
            "sample_index": question["sample_index"],
            "dataset_context_id": dataset_context_id,
            "source_question_id": question["source_question_id"],
            "document_filename": filename,
            "document_id": str(document["id"]),
            "chunk_id": str(selected["chunk_id"]),
            "chunk_index": selected["chunk_index"],
            "chunk_type": selected["chunk_type"],
            "matched_answer": selected["matched_answer"],
            "answer_start": selected["answer_start"],
            "match_offset_in_chunk": selected["match_offset_in_chunk"],
        }
        bindings.append(binding)
        items.append(
            {
                "question": question["question"],
                "reference_answer": question["reference_answer"],
                "expected_chunk_ids": [selected["chunk_id"]],
                "tags": ["CMRC2018", "validation", "20-context-golden"],
                "metadata": {
                    "dataset_id": gold_manifest["dataset_id"],
                    "dataset_context_id": dataset_context_id,
                    "source_context_id": question["source_context_id"],
                    "source_question_id": question["source_question_id"],
                    "document_id": str(document["id"]),
                    "answer_start": selected["answer_start"],
                },
            }
        )

    if len(items) != int(gold_manifest.get("question_count") or 0):
        raise CMRCValidationError("黄金题绑定数量与 manifest 不一致。")
    name = testset_name or f"CMRC2018-validation-20-seed-{gold_manifest['seed']}"
    payload = {
        "knowledge_base_id": knowledge_base_id,
        "name": name,
        "description": (
            "CMRC2018 官方 validation/dev 的 20 题固定黄金集；20 个目标 context + 180 个干扰 context；"
            f"seed={gold_manifest['seed']}。expected_chunk_ids 已在上传处理后按答案原文绑定。"
        ),
        "items": items,
    }
    binding_payload = {
        "schema_version": 1,
        "dataset_id": gold_manifest["dataset_id"],
        "knowledge_base_id": knowledge_base_id,
        "question_count": len(bindings),
        "bindings": bindings,
    }
    _write_json(root / "chunk_bindings.json", binding_payload)
    _write_json(root / "testset.import.json", payload)

    response = None
    if import_testset:
        response = api.create_or_reuse_testset(payload)
        _write_json(root / "testset_response.json", response)
    return {
        "binding_path": str(root / "chunk_bindings.json"),
        "import_payload_path": str(root / "testset.import.json"),
        "testset": response,
        "question_count": len(bindings),
    }


def select_answer_chunk(chunks: list[dict], answers: list[dict]) -> dict:
    candidates: list[tuple[int, int, int, str, dict, dict]] = []
    for chunk in chunks:
        if not chunk.get("is_enabled", True) or chunk.get("chunk_type") == "parent":
            continue
        content = str(chunk.get("content") or "")
        for answer_rank, answer in enumerate(_deduplicate_answers(answers)):
            text = str(answer.get("text") or "")
            if not text:
                continue
            answer_start = int(answer.get("answer_start") or 0)
            offset = content.find(text)
            while offset >= 0:
                absolute_start = int(chunk.get("start_at") or 0) + offset
                candidates.append(
                    (
                        abs(absolute_start - answer_start),
                        answer_rank,
                        int(chunk.get("chunk_index") or 0),
                        str(chunk.get("id") or ""),
                        chunk,
                        {"text": text, "answer_start": answer_start, "offset": offset},
                    )
                )
                offset = content.find(text, offset + 1)
    if not candidates:
        answer_texts = [str(answer.get("text") or "") for answer in answers]
        raise CMRCValidationError(
            "未找到真正包含答案原文的已启用非 parent chunk；"
            f"answers={answer_texts[:3]}，chunk_count={len(chunks)}。"
        )
    _, _, _, _, chunk, answer = min(candidates, key=lambda item: item[:4])
    return {
        "chunk_id": str(chunk["id"]),
        "chunk_index": int(chunk.get("chunk_index") or 0),
        "chunk_type": str(chunk.get("chunk_type") or "child"),
        "matched_answer": answer["text"],
        "answer_start": answer["answer_start"],
        "match_offset_in_chunk": answer["offset"],
    }


def run_native_ragas_comparison(
    api: KnowMateAPI,
    *,
    knowledge_base_id: str,
    testset_id: str,
    output_dir: str | Path,
    top_k: int = 5,
    poll_interval: float = 5.0,
    timeout_per_run: float = 3600.0,
) -> dict:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    variants = [("rerank_off", False), ("rerank_on", True)]
    completed_runs: list[dict] = []
    validation_errors: list[str] = []

    for variant_name, enable_rerank in variants:
        created = api.create_evaluation(
            {
                "knowledge_base_id": knowledge_base_id,
                "testset_id": testset_id,
                "testset_size": 20,
                "top_k": top_k,
                "enable_rerank": enable_rerank,
            }
        )
        detail = _wait_for_evaluation(
            api,
            run_id=str(created["id"]),
            poll_interval=poll_interval,
            timeout=timeout_per_run,
        )
        detail["cmrc_variant"] = variant_name
        completed_runs.append(detail)
        _write_json(output / f"{variant_name}.json", detail)
        mode = ((detail.get("evaluator_config") or {}).get("mode"))
        if detail.get("status") != "completed":
            validation_errors.append(
                f"{variant_name} 未完成：status={detail.get('status')}，error={detail.get('error_message')}"
            )
        if mode != "native_ragas":
            validation_errors.append(
                f"{variant_name} evaluator_config.mode={mode!r}，不是要求的 'native_ragas'。"
            )

    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "knowledge_base_id": knowledge_base_id,
        "testset_id": testset_id,
        "top_k": top_k,
        "required_evaluator_mode": "native_ragas",
        "native_ragas_verified": not validation_errors,
        "judge_limitation": (
            "当前实现的四项 LLM/Embedding 指标使用 native RAGAS，但 factual_correctness 仍是项目的"
            "确定性 proxy；RAGAS 裁判还沿用知识库 qa_model_id。本结果只用于端到端功能验证，"
            "不是使用独立裁判模型、全指标原生实现的正式科研分数。"
        ),
        "validation_errors": validation_errors,
        "runs": [_run_summary(run) for run in completed_runs],
    }
    _write_json(output / "comparison.json", report)
    (output / "comparison.md").write_text(_comparison_markdown(report), encoding="utf-8")
    if validation_errors:
        raise CMRCValidationError(
            "双运行结果已保存，但 native RAGAS 验收失败：" + "；".join(validation_errors)
        )
    return report


class KnowMateAPI:
    def __init__(self, base_url: str, *, timeout: float = 120.0, client: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(base_url=self.base_url, timeout=timeout, follow_redirects=True)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> KnowMateAPI:
        return self

    def __exit__(self, *_exc_info) -> None:
        self.close()

    def health(self) -> dict:
        return self._request("GET", "/health")

    def list_documents(self, knowledge_base_id: str) -> list[dict]:
        return self._request("GET", f"/api/v1/knowledge-bases/{knowledge_base_id}/documents")

    def upload_document(self, knowledge_base_id: str, path: Path) -> dict:
        with path.open("rb") as handle:
            return self._request(
                "POST",
                f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/file",
                files={"file": (path.name, handle, "text/plain; charset=utf-8")},
            )

    def list_document_chunks(self, document_id: str) -> list[dict]:
        return self._request("GET", f"/api/v1/documents/{document_id}/chunks")

    def create_or_reuse_testset(self, payload: dict) -> dict:
        summaries = self._request(
            "GET",
            "/api/v1/evaluations/testsets",
            params={"knowledge_base_id": payload["knowledge_base_id"]},
        )
        matches = [item for item in summaries if item.get("name") == payload["name"]]
        if len(matches) > 1:
            raise CMRCValidationError(f"发现多个同名黄金测试集：{payload['name']}")
        if matches:
            detail = self._request("GET", f"/api/v1/evaluations/testsets/{matches[0]['id']}")
            if not _testset_matches_payload(detail, payload):
                raise CMRCValidationError(
                    f"同名黄金测试集 {payload['name']} 已存在，但题目或 chunk 绑定不同；请更换 --testset-name。"
                )
            return detail | {"reused": True}
        return self._request("POST", "/api/v1/evaluations/testsets", json=payload) | {"reused": False}

    def create_evaluation(self, payload: dict) -> dict:
        return self._request("POST", "/api/v1/evaluations", json=payload)

    def get_evaluation(self, run_id: str) -> dict:
        return self._request("GET", f"/api/v1/evaluations/{run_id}")

    def _request(self, method: str, path: str, **kwargs) -> Any:
        try:
            response = self.client.request(method, path, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json().get("detail")
            except (ValueError, AttributeError):
                detail = exc.response.text
            raise CMRCValidationError(
                f"KnowMate API {method} {path} 返回 {exc.response.status_code}：{detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise CMRCValidationError(f"KnowMate API {method} {path} 调用失败：{exc}") from exc
        try:
            return response.json()
        except ValueError as exc:
            raise CMRCValidationError(f"KnowMate API {method} {path} 未返回 JSON。") from exc


def _cmrc_context_records(source_payload: dict) -> list[dict]:
    if not isinstance(source_payload.get("data"), list):
        raise CMRCValidationError("CMRC2018 JSON 缺少 data 列表。")
    records: list[dict] = []
    seen_ids: set[str] = set()
    seen_context_hashes: set[str] = set()
    for article_index, article in enumerate(source_payload["data"]):
        article_id = str(article.get("id") or f"article-{article_index}")
        title = str(article.get("title") or "")
        for paragraph_index, paragraph in enumerate(article.get("paragraphs") or []):
            source_context_id = str(paragraph.get("id") or f"{article_id}-p{paragraph_index}")
            context = str(paragraph.get("context") or "")
            context_hash = _sha256(context.encode("utf-8"))
            if not context.strip():
                continue
            if source_context_id in seen_ids:
                raise CMRCValidationError(f"CMRC2018 source context ID 重复：{source_context_id}")
            if context_hash in seen_context_hashes:
                continue
            seen_ids.add(source_context_id)
            seen_context_hashes.add(context_hash)
            valid_qas: list[dict] = []
            for qa in paragraph.get("qas") or []:
                valid_answers = [
                    {"text": str(answer.get("text") or ""), "answer_start": int(answer.get("answer_start") or 0)}
                    for answer in (qa.get("answers") or [])
                    if _answer_is_exact(context, answer)
                ]
                question = str(qa.get("question") or "").strip()
                if question and valid_answers:
                    valid_qas.append(
                        {
                            "id": str(qa.get("id") or ""),
                            "question": question,
                            "valid_answers": valid_answers,
                        }
                    )
            if valid_qas:
                records.append(
                    {
                        "source_context_id": source_context_id,
                        "source_article_id": article_id,
                        "source_title": title,
                        "context": context,
                        "valid_qas": valid_qas,
                    }
                )
    return records


def _select_records(
    records: list[dict],
    *,
    seed: int,
    target_count: int,
    distractor_count: int,
) -> tuple[list[dict], list[dict]]:
    required = target_count + distractor_count
    if len(records) < required:
        raise CMRCValidationError(f"有效且互异的 context 只有 {len(records)} 篇，少于所需 {required} 篇。")
    shuffled = sorted(records, key=lambda item: item["source_context_id"])
    random.Random(seed).shuffle(shuffled)
    return shuffled[:target_count], shuffled[target_count:required]


def _validate_prepared_dataset(root: Path, record_by_id: dict[str, dict]) -> None:
    manifest = _read_json(root / "corpus_manifest.json")
    gold = _read_json(root / "golden_questions.raw.json")
    contexts = manifest["contexts"]
    context_ids = [item["dataset_context_id"] for item in contexts]
    target_ids = {item["dataset_context_id"] for item in contexts if item["role"] == "target"}
    gold_context_ids = {item["dataset_context_id"] for item in gold["questions"]}
    if len(contexts) != 200 or len(set(context_ids)) != 200:
        raise CMRCValidationError("转换结果必须恰好包含 200 篇互不相同的 context。")
    if len(target_ids) != 20 or gold_context_ids != target_ids or len(gold["questions"]) != 20:
        raise CMRCValidationError("转换结果必须是 20 个目标 context 对应 20 道黄金题。")
    for item in contexts:
        source_context_id = str(item["source_context_id"])
        path = root / "corpus" / str(item["document_filename"])
        expected_context = record_by_id[source_context_id]["context"]
        if path.read_text(encoding="utf-8") != expected_context:
            raise CMRCValidationError(f"上传文档不是纯原始 context：{path.name}")
        _verify_context_file(path, item)


def _wait_for_documents(
    api: KnowMateAPI,
    *,
    knowledge_base_id: str,
    document_ids: set[str],
    poll_interval: float,
    timeout: float,
) -> list[dict]:
    deadline = time.monotonic() + timeout
    while True:
        documents = api.list_documents(knowledge_base_id)
        selected = [document for document in documents if str(document.get("id")) in document_ids]
        by_id = {str(document["id"]): document for document in selected}
        missing = document_ids - set(by_id)
        if missing:
            raise CMRCValidationError(f"上传后的文档未出现在当前知识库：{sorted(missing)[:3]}")
        failed = [
            document for document in selected if document.get("parse_status") in {"failed", "cancelled"}
        ]
        if failed:
            summary = [
                f"{document.get('file_name')}={document.get('parse_status')}: {document.get('error_message')}"
                for document in failed[:5]
            ]
            raise CMRCValidationError("文档处理失败：" + "；".join(summary))
        if all(document.get("parse_status") == "completed" for document in selected):
            return selected
        if time.monotonic() >= deadline:
            pending = [
                f"{document.get('file_name')}={document.get('parse_status')}" for document in selected
                if document.get("parse_status") not in TERMINAL_DOCUMENT_STATUSES
            ]
            raise CMRCValidationError(f"等待文档处理超时；仍未完成：{pending[:5]}")
        time.sleep(poll_interval)


def _wait_for_evaluation(
    api: KnowMateAPI,
    *,
    run_id: str,
    poll_interval: float,
    timeout: float,
) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        detail = api.get_evaluation(run_id)
        if detail.get("status") in TERMINAL_EVALUATION_STATUSES:
            return detail
        if time.monotonic() >= deadline:
            raise CMRCValidationError(f"等待评测 {run_id} 超时，当前状态：{detail.get('status')}")
        time.sleep(poll_interval)


def _documents_by_filename(documents: list[dict]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for document in documents:
        filename = str(document.get("file_name") or document.get("title") or "")
        if not filename:
            continue
        if filename in result:
            raise CMRCValidationError(f"当前知识库存在同名活动文档，无法稳定映射：{filename}")
        result[filename] = document
    return result


def _document_mapping(context: dict, document: dict) -> dict:
    return {
        "dataset_context_id": context["dataset_context_id"],
        "source_context_id": context["source_context_id"],
        "document_filename": context["document_filename"],
        "role": context["role"],
        "document_id": str(document["id"]),
        "parse_status": document.get("parse_status"),
        "chunk_count": int(document.get("chunk_count") or 0),
    }


def _testset_matches_payload(detail: dict, payload: dict) -> bool:
    actual_items = detail.get("items") or []
    expected_items = payload.get("items") or []
    if detail.get("knowledge_base_id") != payload.get("knowledge_base_id") or len(actual_items) != len(expected_items):
        return False
    for actual, expected in zip(actual_items, expected_items, strict=True):
        if actual.get("question") != expected.get("question"):
            return False
        if actual.get("reference_answer") != expected.get("reference_answer"):
            return False
        if [str(value) for value in actual.get("expected_chunk_ids") or []] != [
            str(value) for value in expected.get("expected_chunk_ids") or []
        ]:
            return False
    return True


def _run_summary(run: dict) -> dict:
    metrics_summary = run.get("metrics_summary") or {}
    metrics = metrics_summary.get("metrics") or {}
    return {
        "variant": run.get("cmrc_variant"),
        "run_id": run.get("id"),
        "status": run.get("status"),
        "top_k": run.get("top_k"),
        "enable_rerank": run.get("enable_rerank"),
        "evaluator_mode": (run.get("evaluator_config") or {}).get("mode"),
        "overall_score": metrics_summary.get("overall_score"),
        "metrics": {name: payload.get("average") for name, payload in metrics.items()},
        "sample_count": run.get("sample_count"),
        "completed_sample_count": run.get("completed_sample_count"),
        "failed_sample_count": run.get("failed_sample_count"),
        "expected_source_hit_rate": _expected_source_hit_rate(run.get("samples") or []),
        "error_message": run.get("error_message"),
    }


def _expected_source_hit_rate(samples: list[dict]) -> float | None:
    values = [
        bool((sample.get("diagnostics") or {}).get("expected_source_hit"))
        for sample in samples
        if (sample.get("diagnostics") or {}).get("expected_source_hit") is not None
    ]
    return round(sum(values) / len(values), 4) if values else None


def _comparison_markdown(report: dict) -> str:
    lines = [
        "# CMRC2018 端到端评测结果",
        "",
        f"- knowledge_base_id: `{report['knowledge_base_id']}`",
        f"- testset_id: `{report['testset_id']}`",
        f"- top_k: `{report['top_k']}`",
        f"- native RAGAS 验证: `{'通过' if report['native_ragas_verified'] else '失败'}`",
        f"- 重要局限: {report['judge_limitation']}",
        "",
        "| 变体 | rerank | 状态 | evaluator mode | overall | expected source hit rate | 失败题数 |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for run in report["runs"]:
        lines.append(
            "| {variant} | {rerank} | {status} | {mode} | {overall} | {hit_rate} | {failed} |".format(
                variant=run["variant"],
                rerank=str(run["enable_rerank"]).lower(),
                status=run["status"],
                mode=run["evaluator_mode"],
                overall=_display_score(run["overall_score"]),
                hit_rate=_display_score(run["expected_source_hit_rate"]),
                failed=run["failed_sample_count"],
            )
        )
    lines.extend(["", "## 指标", ""])
    metric_names = sorted({name for run in report["runs"] for name in run["metrics"]})
    lines.append("| 变体 | " + " | ".join(metric_names) + " |")
    lines.append("| --- | " + " | ".join("---:" for _ in metric_names) + " |")
    for run in report["runs"]:
        lines.append(
            f"| {run['variant']} | "
            + " | ".join(_display_score(run["metrics"].get(name)) for name in metric_names)
            + " |"
        )
    if report["validation_errors"]:
        lines.extend(["", "## 验收错误", ""])
        lines.extend(f"- {error}" for error in report["validation_errors"])
    return "\n".join(lines) + "\n"


def _display_score(value: Any) -> str:
    return "-" if value is None else f"{float(value):.4f}"


def _answer_is_exact(context: str, answer: dict) -> bool:
    text = str(answer.get("text") or "")
    try:
        start = int(answer.get("answer_start"))
    except (TypeError, ValueError):
        return False
    return bool(text) and start >= 0 and context[start : start + len(text)] == text


def _deduplicate_answers(answers: list[dict]) -> list[dict]:
    result: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for answer in answers:
        item = (str(answer.get("text") or ""), int(answer.get("answer_start") or 0))
        if not item[0] or item in seen:
            continue
        seen.add(item)
        result.append({"text": item[0], "answer_start": item[1]})
    return result


def _dataset_context_id(source_context_id: str) -> str:
    return f"cmrc2018:validation:{source_context_id}"


def _document_filename(source_context_id: str) -> str:
    safe_id = "".join(
        character if character.isalnum() or character in "._-" else "_"
        for character in source_context_id
    )
    return f"cmrc2018_validation__{safe_id}.txt"


def _verify_context_file(path: Path, context: dict) -> None:
    if not path.is_file():
        raise CMRCValidationError(f"缺少上传文档：{path}")
    content = path.read_bytes()
    if _sha256(content) != context["context_sha256"] or len(content) != int(context["context_bytes"]):
        raise CMRCValidationError(f"上传文档与 corpus manifest 不一致：{path.name}")


def _download_verified(url: str, expected_sha256: str) -> bytes:
    try:
        response = httpx.get(url, timeout=120.0, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise CMRCValidationError(f"下载 CMRC2018 官方资源失败：{url}：{exc}") from exc
    content = response.content
    actual_sha256 = _sha256(content)
    if actual_sha256 != expected_sha256:
        raise CMRCValidationError(
            f"CMRC2018 官方资源校验失败：{url}，期望 {expected_sha256}，实际 {actual_sha256}。"
        )
    return content


def _source_metadata() -> dict:
    return {
        "repository": "https://github.com/ymcui/cmrc2018",
        "commit": CMRC2018_COMMIT,
        "file": "squad-style-data/cmrc2018_dev.json",
        "download_url": CMRC2018_DEV_URL,
        "sha256": CMRC2018_DEV_SHA256,
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
    }


def _source_and_license_text() -> str:
    return f"""# CMRC2018 数据来源与许可证

本目录使用 CMRC2018 官方仓库的 validation/development 数据文件：

- 官方仓库：https://github.com/ymcui/cmrc2018
- 锁定提交：`{CMRC2018_COMMIT}`
- 原始文件：`squad-style-data/cmrc2018_dev.json`
- 原始文件 SHA-256：`{CMRC2018_DEV_SHA256}`
- 官方数据集页面：https://ymcui.com/cmrc2018/
- 论文：Cui et al., *A Span-Extraction Dataset for Chinese Machine Reading Comprehension*,
  EMNLP-IJCNLP 2019, DOI 10.18653/v1/D19-1600

CMRC2018 官方页面和仓库声明数据采用 **Creative Commons Attribution-ShareAlike 4.0
International（CC BY-SA 4.0）**。许可证全文保存在 `source/CMRC2018_LICENCE.txt`，
许可证网址为 https://creativecommons.org/licenses/by-sa/4.0/ 。使用或再分发这些数据及其
派生数据时需要保留署名，并按相同许可证共享。

`corpus/` 中的 200 个 `.txt` 文件逐字节只包含官方 context，不包含 question 或 answer。
question/answer 仅存在于 `source/cmrc2018_dev.json` 和 `golden_questions.raw.json`，不得把这两个文件上传到知识库。
"""


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CMRCValidationError(f"缺少文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise CMRCValidationError(f"JSON 文件无法解析：{path}：{exc}") from exc


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
