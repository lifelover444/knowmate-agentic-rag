from collections.abc import Iterable
from copy import deepcopy

from app.rag.retriever import tokenize_query


class OpenSearchSparseStore:
    """Minimal sparse/BM25-style store boundary for fake/test-client coverage."""

    def __init__(self, config: dict | None = None, *, client=None) -> None:
        self.config = config or {}
        self.client = client or self.config.get("client")
        self.index_name = str(self.config.get("index_name") or self.config.get("index") or "knowmate_chunks")
        self._fake_enabled = bool(self.config.get("fake"))
        self._documents: dict[str, dict] = {}

    def test_connection(self) -> None:
        if self._fake_enabled or self.client is not None:
            if hasattr(self.client, "ping") and not self.client.ping():
                raise ValueError("OpenSearch/Elasticsearch sparse 检索服务连接失败")
            return
        if not self.config.get("endpoint") and not self.config.get("hosts"):
            raise ValueError("OpenSearch/Elasticsearch sparse 检索服务未配置")
        raise ValueError("OpenSearch/Elasticsearch sparse 检索真实客户端尚未启用，请配置 fake 或测试 client")

    def upsert_chunks(self, *, vectors: list[list[float]], payloads: list[dict]) -> None:
        if self.client is not None and not self._fake_enabled and hasattr(self.client, "bulk"):
            self.client.bulk(self._bulk_actions(payloads))
            return
        for payload in payloads:
            normalized = self._normalize_payload(payload)
            self._documents[normalized["chunk_id"]] = normalized

    def delete_by_knowledge_id(self, knowledge_id: str) -> None:
        self._documents = {
            chunk_id: payload
            for chunk_id, payload in self._documents.items()
            if str(payload.get("knowledge_id")) != knowledge_id
        }

    def set_tag_for_knowledge_ids(self, *, knowledge_ids: list[str], tag_id: str | None) -> None:
        if not knowledge_ids:
            return
        allowed = set(knowledge_ids)
        for payload in self._documents.values():
            if str(payload.get("knowledge_id")) in allowed:
                payload["tag_id"] = tag_id

    def set_enabled_for_chunk_ids(self, *, chunk_ids: list[str], is_enabled: bool) -> None:
        self.set_payload_for_chunk_ids(chunk_ids=chunk_ids, payload={"is_enabled": is_enabled})

    def set_payload_for_chunk_ids(self, *, chunk_ids: list[str], payload: dict) -> None:
        if not chunk_ids or not payload:
            return
        allowed = set(chunk_ids)
        for chunk_id, stored in self._documents.items():
            if chunk_id not in allowed:
                continue
            merged = deepcopy(payload)
            if isinstance(merged.get("metadata"), dict) and isinstance(stored.get("metadata"), dict):
                merged["metadata"] = {**stored["metadata"], **merged["metadata"]}
            stored.update(merged)

    def move_knowledge_to_kb(self, *, knowledge_id: str, target_kb_id: str) -> None:
        for payload in self._documents.values():
            if str(payload.get("knowledge_id")) == knowledge_id:
                payload["knowledge_base_id"] = target_kb_id
                payload["tag_id"] = None

    def search_text(
        self,
        *,
        knowledge_base_id: str,
        query: str,
        limit: int,
        score_threshold: float | None = None,
        knowledge_ids: list[str] | None = None,
    ) -> list[dict]:
        terms = tokenize_query(query)
        if not terms:
            return []
        allowed_knowledge_ids = set(knowledge_ids or [])
        hits: list[dict] = []
        for payload in self._documents.values():
            if str(payload.get("knowledge_base_id")) != knowledge_base_id:
                continue
            if allowed_knowledge_ids and str(payload.get("knowledge_id")) not in allowed_knowledge_ids:
                continue
            if payload.get("is_enabled") is False:
                continue
            score = _sparse_score(terms, _searchable_text(payload))
            if score <= 0:
                continue
            if score_threshold is not None and score < score_threshold:
                continue
            hit = deepcopy(payload)
            hit["score"] = score
            hits.append(hit)
        hits.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
        return hits[:limit]

    def _normalize_payload(self, payload: dict) -> dict:
        normalized = deepcopy(payload)
        normalized["chunk_id"] = str(normalized["chunk_id"])
        normalized["knowledge_id"] = str(normalized["knowledge_id"])
        normalized["knowledge_base_id"] = str(normalized["knowledge_base_id"])
        normalized["content"] = str(normalized.get("content") or "")
        normalized["search_text"] = str(normalized.get("search_text") or normalized["content"])
        normalized["metadata"] = normalized.get("metadata") or {}
        normalized["is_enabled"] = bool(normalized.get("is_enabled", True))
        return normalized

    def _bulk_actions(self, payloads: Iterable[dict]) -> list[dict]:
        return [
            {
                "_op_type": "index",
                "_index": self.index_name,
                "_id": str(payload.get("chunk_id")),
                "_source": self._normalize_payload(payload),
            }
            for payload in payloads
        ]


def _searchable_text(payload: dict) -> str:
    fields = [
        payload.get("search_text"),
        payload.get("content"),
        payload.get("context_header"),
        payload.get("title"),
    ]
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        fields.extend(str(value) for value in metadata.values() if isinstance(value, str | int | float))
    return " ".join(str(item) for item in fields if item).lower()


def _sparse_score(terms: list[str], searchable: str) -> float:
    if not searchable:
        return 0.0
    total = 0.0
    for term in terms:
        normalized = term.lower()
        if not normalized:
            continue
        count = searchable.count(normalized)
        if count:
            total += 1.0 + min(count - 1, 3) * 0.2
    return round(total / max(len(terms), 1), 6)
