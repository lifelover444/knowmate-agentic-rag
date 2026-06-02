from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.core.config import Settings


class QdrantVectorStore:
    def __init__(self, settings: Settings, config: dict | None = None) -> None:
        config = config or {}
        self.base_collection = str(config.get("collection") or settings.qdrant_collection)
        self.client = QdrantClient(
            host=str(config.get("host") or settings.qdrant_host),
            port=int(config.get("port") or settings.qdrant_port),
            api_key=config.get("api_key") or settings.qdrant_api_key or None,
            https=bool(config.get("use_tls", settings.qdrant_use_tls)),
            check_compatibility=False,
        )

    def test_connection(self) -> None:
        self.client.get_collections()

    def collection_name(self, dimension: int) -> str:
        return f"{self.base_collection}_{dimension}"

    def ensure_collection(self, dimension: int) -> None:
        collection = self.collection_name(dimension)
        collections = {item.name for item in self.client.get_collections().collections}
        if collection not in collections:
            self.client.create_collection(
                collection_name=collection,
                vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
            )
            for field, schema in {
                "chunk_id": models.PayloadSchemaType.KEYWORD,
                "knowledge_id": models.PayloadSchemaType.KEYWORD,
                "knowledge_base_id": models.PayloadSchemaType.KEYWORD,
                "source_id": models.PayloadSchemaType.KEYWORD,
                "parent_chunk_id": models.PayloadSchemaType.KEYWORD,
                "tag_id": models.PayloadSchemaType.KEYWORD,
                "chunk_type": models.PayloadSchemaType.KEYWORD,
                "is_enabled": models.PayloadSchemaType.BOOL,
                "content": models.PayloadSchemaType.TEXT,
                "context_header": models.PayloadSchemaType.TEXT,
            }.items():
                self.client.create_payload_index(collection_name=collection, field_name=field, field_schema=schema)

    def upsert_chunks(self, *, vectors: list[list[float]], payloads: list[dict]) -> None:
        if not vectors:
            return
        dimension = len(vectors[0])
        self.ensure_collection(dimension)
        points = [
            models.PointStruct(id=payload["chunk_id"], vector=vector, payload=payload)
            for vector, payload in zip(vectors, payloads, strict=True)
        ]
        self.client.upsert(collection_name=self.collection_name(dimension), points=points)

    def delete_by_knowledge_id(self, knowledge_id: str) -> None:
        for collection in self.client.get_collections().collections:
            if not collection.name.startswith(f"{self.base_collection}_"):
                continue
            self.client.delete(
                collection_name=collection.name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="knowledge_id",
                                match=models.MatchValue(value=knowledge_id),
                            )
                        ]
                    )
                ),
            )

    def set_tag_for_knowledge_ids(self, *, knowledge_ids: list[str], tag_id: str | None) -> None:
        if not knowledge_ids:
            return
        for collection in self.client.get_collections().collections:
            if not collection.name.startswith(f"{self.base_collection}_"):
                continue
            self.client.set_payload(
                collection_name=collection.name,
                payload={"tag_id": tag_id},
                points=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="knowledge_id",
                            match=models.MatchAny(any=knowledge_ids),
                        )
                    ]
                ),
            )

    def move_knowledge_to_kb(self, *, knowledge_id: str, target_kb_id: str) -> None:
        for collection in self.client.get_collections().collections:
            if not collection.name.startswith(f"{self.base_collection}_"):
                continue
            self.client.set_payload(
                collection_name=collection.name,
                payload={"knowledge_base_id": target_kb_id, "tag_id": None},
                points=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="knowledge_id",
                            match=models.MatchValue(value=knowledge_id),
                        )
                    ]
                ),
            )

    def search(
        self,
        *,
        knowledge_base_id: str,
        query_vector: list[float],
        limit: int,
        score_threshold: float | None = None,
        knowledge_ids: list[str] | None = None,
    ) -> list[dict]:
        dimension = len(query_vector)
        collection = self.collection_name(dimension)
        collections = {item.name for item in self.client.get_collections().collections}
        if collection not in collections:
            return []
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="knowledge_base_id",
                    match=models.MatchValue(value=knowledge_base_id),
                ),
                models.FieldCondition(key="is_enabled", match=models.MatchValue(value=True)),
            ]
        )
        if knowledge_ids:
            query_filter.must.append(
                models.FieldCondition(
                    key="knowledge_id",
                    match=models.MatchAny(any=knowledge_ids),
                )
            )
        if hasattr(self.client, "search"):
            results = self.client.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=limit,
                query_filter=query_filter,
                with_payload=True,
                score_threshold=score_threshold,
            )
        else:
            results = self.client.query_points(
                collection_name=collection,
                query=query_vector,
                limit=limit,
                query_filter=query_filter,
                with_payload=True,
                score_threshold=score_threshold,
            ).points
        return [
            {
                "chunk_id": str(hit.payload.get("chunk_id")),
                "knowledge_id": str(hit.payload.get("knowledge_id")),
                "knowledge_base_id": str(hit.payload.get("knowledge_base_id")),
                "content": str(hit.payload.get("content")),
                "context_header": hit.payload.get("context_header"),
                "parent_chunk_id": hit.payload.get("parent_chunk_id"),
                "tag_id": hit.payload.get("tag_id"),
                "chunk_type": hit.payload.get("chunk_type"),
                "metadata": hit.payload.get("metadata") or {},
                "title": hit.payload.get("title"),
                "score": float(hit.score),
            }
            for hit in results
        ]
