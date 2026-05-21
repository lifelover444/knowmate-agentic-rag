from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.core.config import Settings


class QdrantVectorStore:
    def __init__(self, settings: Settings) -> None:
        self.base_collection = settings.qdrant_collection
        self.client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            api_key=settings.qdrant_api_key or None,
            https=settings.qdrant_use_tls,
        )

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
                "is_enabled": models.PayloadSchemaType.BOOL,
                "content": models.PayloadSchemaType.TEXT,
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

    def search(self, *, knowledge_base_id: str, query_vector: list[float], limit: int) -> list[dict]:
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
        if hasattr(self.client, "search"):
            results = self.client.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=limit,
                query_filter=query_filter,
                with_payload=True,
            )
        else:
            results = self.client.query_points(
                collection_name=collection,
                query=query_vector,
                limit=limit,
                query_filter=query_filter,
                with_payload=True,
            ).points
        return [
            {
                "chunk_id": str(hit.payload.get("chunk_id")),
                "knowledge_id": str(hit.payload.get("knowledge_id")),
                "knowledge_base_id": str(hit.payload.get("knowledge_base_id")),
                "content": str(hit.payload.get("content")),
                "title": hit.payload.get("title"),
                "score": float(hit.score),
            }
            for hit in results
        ]
