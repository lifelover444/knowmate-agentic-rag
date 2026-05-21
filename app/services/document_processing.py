import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import Chunk
from app.db.repositories.chunk import ChunkRepository
from app.db.repositories.document import DocumentRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.rag.chunker import TextChunker
from app.rag.parser import DocumentParser


class DocumentProcessingService:
    def __init__(self, db: Session, upload_dir: Path, embedder, vector_store) -> None:
        self.db = db
        self.upload_dir = upload_dir
        self.embedder = embedder
        self.vector_store = vector_store
        self.documents = DocumentRepository(db)
        self.knowledge_bases = KnowledgeBaseRepository(db)
        self.chunks = ChunkRepository(db)

    def process(self, document_id: str) -> None:
        document = self.documents.get(document_id)
        if document is None:
            raise LookupError("document not found")
        kb = self.knowledge_bases.get(document.knowledge_base_id, document.tenant_id)
        if kb is None:
            raise LookupError("knowledge base not found")

        document.parse_status = "processing"
        self.documents.save(document)
        try:
            parsed = DocumentParser().parse(Path(document.file_path or ""))
            chunking = kb.chunking_config or {}
            parsed_chunks = TextChunker(
                chunk_size=int(chunking.get("chunk_size", 512)),
                chunk_overlap=int(chunking.get("chunk_overlap", 80)),
            ).split(parsed.text)
            db_chunks = [
                Chunk(
                    id=str(uuid.uuid4()),
                    tenant_id=document.tenant_id,
                    knowledge_base_id=document.knowledge_base_id,
                    knowledge_id=document.id,
                    content=item.content,
                    chunk_index=item.index,
                    is_enabled=True,
                    start_at=item.start,
                    end_at=item.end,
                    chunk_type="text",
                )
                for item in parsed_chunks
            ]
            for idx, chunk in enumerate(db_chunks):
                if idx > 0:
                    chunk.pre_chunk_id = db_chunks[idx - 1].id
                if idx < len(db_chunks) - 1:
                    chunk.next_chunk_id = db_chunks[idx + 1].id
            self.chunks.replace_for_document(document.id, db_chunks)

            contents = [chunk.content for chunk in db_chunks]
            vectors = self.embedder.embed_many(contents)
            payloads = [
                {
                    "content": chunk.content,
                    "source_id": chunk.id,
                    "source_type": 1,
                    "chunk_id": chunk.id,
                    "knowledge_id": document.id,
                    "knowledge_base_id": document.knowledge_base_id,
                    "title": document.title,
                    "is_enabled": chunk.is_enabled,
                }
                for chunk in db_chunks
            ]
            self.vector_store.upsert_chunks(vectors=vectors, payloads=payloads)

            document.parse_status = "completed"
            document.error_message = None
            document.processed_at = datetime.now(UTC)
            self.documents.save(document)
        except Exception as exc:
            document.parse_status = "failed"
            document.error_message = str(exc)
            self.documents.save(document)
            raise
