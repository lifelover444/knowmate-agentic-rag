import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Chunk
from app.db.repositories.chunk import ChunkRepository
from app.db.repositories.document import DocumentRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.integrations.llm_openai import OpenAIEmbedder
from app.rag.chunker import AdaptiveTextChunker, ChunkingConfig, ParsedChunk, split_parent_child
from app.rag.parser import DocumentParser
from app.services.knowledge_base import normalize_chunking_config
from app.services.model_config import ModelConfigService


class DocumentProcessingService:
    def __init__(self, db: Session, upload_dir: Path, vector_store, settings=None, embedder=None) -> None:
        self.db = db
        self.upload_dir = upload_dir
        self.embedder = embedder
        self.vector_store = vector_store
        self.settings = settings or Settings()
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
            file_path = Path(document.file_path or "")
            parsed = DocumentParser().parse(
                file_path,
                engine=_select_parser_engine(kb.parser_engine_rules, document.file_type),
            )
            document.doc_metadata = {**(document.doc_metadata or {}), **parsed.metadata, "pages": parsed.pages}
            chunking = normalize_chunking_config(kb.chunking_config, self.settings)
            db_chunks, embedding_chunks = _build_db_chunks(
                document=document,
                text=parsed.content,
                chunking=chunking,
            )
            for idx, chunk in enumerate(db_chunks):
                if idx > 0:
                    chunk.pre_chunk_id = db_chunks[idx - 1].id
                if idx < len(db_chunks) - 1:
                    chunk.next_chunk_id = db_chunks[idx + 1].id
            if hasattr(self.vector_store, "delete_by_knowledge_id"):
                self.vector_store.delete_by_knowledge_id(document.id)
            self.chunks.replace_for_document(document.id, db_chunks)

            contents = [_embedding_content(chunk) for chunk in embedding_chunks]
            embedder = self.embedder
            if embedder is None:
                runtime_config = ModelConfigService(self.db, self.settings).build_runtime_config_for_model(
                    kb.embedding_model_id,
                    "Embedding",
                )
                embedder = OpenAIEmbedder(runtime_config)
            vectors = embedder.embed_many(contents)
            payloads = [
                {
                    "content": chunk.content,
                    "context_header": chunk.context_header,
                    "source_id": chunk.id,
                    "source_type": 1,
                    "chunk_id": chunk.id,
                    "knowledge_id": document.id,
                    "knowledge_base_id": document.knowledge_base_id,
                    "title": document.title,
                    "is_enabled": chunk.is_enabled,
                    "parent_chunk_id": chunk.parent_chunk_id,
                    "chunk_type": chunk.chunk_type,
                    "metadata": chunk.chunk_metadata or {},
                }
                for chunk in embedding_chunks
            ]
            self.vector_store.upsert_chunks(vectors=vectors, payloads=payloads)

            document.parse_status = "completed"
            document.error_message = None
            document.embedding_model_id = kb.embedding_model_id
            document.processed_at = datetime.now(UTC)
            self.documents.save(document)
        except Exception as exc:
            document.parse_status = "failed"
            document.error_message = str(exc)
            self.documents.save(document)
            raise


def _select_parser_engine(rules: list | None, file_type: str | None) -> str | None:
    normalized = (file_type or "").lower().lstrip(".")
    for rule in rules or []:
        if normalized in {item.lower().lstrip(".") for item in rule.get("file_types", [])}:
            return rule.get("engine")
    return "builtin"


def _chunking_config(data: dict, *, size_key: str = "chunk_size") -> ChunkingConfig:
    return ChunkingConfig(
        chunk_size=int(data.get(size_key, data.get("chunk_size", 512))),
        chunk_overlap=int(data.get("chunk_overlap", 80)),
        separators=list(data.get("separators") or ["\n\n", "\n", "。"]),
        strategy=str(data.get("strategy") or "auto"),
        token_limit=int(data.get("token_limit") or 0),
        languages=list(data.get("languages") or []),
    )


def _build_db_chunks(document, text: str, chunking: dict) -> tuple[list[Chunk], list[Chunk]]:
    if chunking.get("enable_parent_child"):
        result = split_parent_child(
            text,
            parent_config=_chunking_config(chunking, size_key="parent_chunk_size"),
            child_config=_chunking_config(chunking, size_key="child_chunk_size"),
        )
        db_chunks: list[Chunk] = []
        parent_ids: list[str] = []
        for parent in result.parents:
            chunk = _to_db_chunk(document, parent, len(db_chunks), "parent")
            db_chunks.append(chunk)
            parent_ids.append(chunk.id)
        embedding_chunks: list[Chunk] = []
        for child in result.children:
            chunk = _to_db_chunk(document, child.chunk, len(db_chunks), "child")
            chunk.parent_chunk_id = parent_ids[child.parent_index]
            db_chunks.append(chunk)
            embedding_chunks.append(chunk)
        return db_chunks, embedding_chunks

    parsed_chunks = AdaptiveTextChunker(_chunking_config(chunking)).split(text)
    db_chunks = [_to_db_chunk(document, item, item.index, "text") for item in parsed_chunks]
    return db_chunks, db_chunks


def _to_db_chunk(document, item: ParsedChunk, index: int, chunk_type: str) -> Chunk:
    metadata = {**(item.metadata or {}), "title": document.title}
    search_text = _search_text(document.title, item.context_header, item.content)
    return Chunk(
        id=str(uuid.uuid4()),
        tenant_id=document.tenant_id,
        knowledge_base_id=document.knowledge_base_id,
        knowledge_id=document.id,
        content=item.content,
        search_text=search_text,
        chunk_index=index,
        is_enabled=True,
        start_at=item.start,
        end_at=item.end,
        chunk_type=chunk_type,
        context_header=item.context_header or None,
        chunk_metadata=metadata,
        images=item.images or [],
    )


def _embedding_content(chunk: Chunk) -> str:
    content = chunk.content.strip()
    return f"{chunk.context_header}\n\n{content}" if chunk.context_header else content


def _search_text(title: str | None, context_header: str | None, content: str) -> str:
    return "\n".join(item for item in (title, context_header, content) if item).strip()
