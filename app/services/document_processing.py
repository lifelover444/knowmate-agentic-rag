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
from app.services.processing_spans import ProcessingSpanService


class DocumentProcessingCancelled(RuntimeError):
    pass


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
        if document.parse_status == "cancelled":
            return
        kb = self.knowledge_bases.get(document.knowledge_base_id, document.tenant_id)
        if kb is None:
            raise LookupError("knowledge base not found")

        spans = ProcessingSpanService(self.db)
        attempt = spans.open_attempt(document)
        current_stage: str | None = None
        document.parse_status = "processing"
        self.documents.save(document)
        try:
            current_stage = "parse"
            spans.begin_stage(
                document.id,
                attempt,
                current_stage,
                input_json={"file_path": document.file_path, "file_type": document.file_type},
            )
            self._raise_if_cancelled(document)
            file_path = Path(document.file_path or "")
            parsed = DocumentParser().parse(
                file_path,
                engine=_select_parser_engine(kb.parser_engine_rules, document.file_type),
            )
            if not parsed.content.strip():
                raise ValueError("未解析出可入库文本；该文件可能是扫描版或图片型 PDF，请接入 OCR/MinerU 后重试。")
            document.doc_metadata = {**(document.doc_metadata or {}), **parsed.metadata, "pages": parsed.pages}
            spans.end_stage(document.id, attempt, current_stage, output_json={"pages": parsed.pages})

            current_stage = "chunk"
            self._raise_if_cancelled(document)
            spans.begin_stage(document.id, attempt, current_stage, input_json={"content_length": len(parsed.content)})
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
            spans.end_stage(
                document.id,
                attempt,
                current_stage,
                output_json={"chunk_count": len(db_chunks), "embedding_chunk_count": len(embedding_chunks)},
            )

            current_stage = "embed"
            self._raise_if_cancelled(document)
            spans.begin_stage(document.id, attempt, current_stage, input_json={"chunk_count": len(embedding_chunks)})
            contents = [_embedding_content(chunk) for chunk in embedding_chunks]
            embedder = self.embedder
            if embedder is None:
                runtime_config = ModelConfigService(self.db, self.settings).build_runtime_config_for_model(
                    kb.embedding_model_id,
                    "Embedding",
                )
                embedder = OpenAIEmbedder(runtime_config)
            vectors = embedder.embed_many(contents)
            spans.end_stage(document.id, attempt, current_stage, output_json={"vector_count": len(vectors)})

            current_stage = "upsert"
            self._raise_if_cancelled(document)
            spans.begin_stage(document.id, attempt, current_stage, input_json={"vector_count": len(vectors)})
            if hasattr(self.vector_store, "delete_by_knowledge_id"):
                self.vector_store.delete_by_knowledge_id(document.id)
            self.chunks.bm25_delete_by_document(document.id)
            self.chunks.replace_for_document(document.id, db_chunks)
            self.chunks.bm25_upsert_chunks(embedding_chunks)
            payloads = [
                {
                    "content": chunk.content,
                    "search_text": chunk.search_text,
                    "context_header": chunk.context_header,
                    "source_id": chunk.id,
                    "source_type": 1,
                    "chunk_id": chunk.id,
                    "child_chunk_id": chunk.id,
                    "knowledge_id": document.id,
                    "document_id": document.id,
                    "knowledge_base_id": document.knowledge_base_id,
                    "tenant_id": document.tenant_id,
                    "title": document.title,
                    "is_enabled": chunk.is_enabled,
                    "parent_chunk_id": chunk.parent_chunk_id,
                    "tag_id": chunk.tag_id,
                    "chunk_type": chunk.chunk_type,
                    "position": chunk.chunk_index,
                    "index": chunk.chunk_index,
                    "metadata": chunk.chunk_metadata or {},
                }
                for chunk in embedding_chunks
            ]
            self.vector_store.upsert_chunks(vectors=vectors, payloads=payloads)
            spans.end_stage(document.id, attempt, current_stage, output_json={"payload_count": len(payloads)})

            current_stage = "finalize"
            self._raise_if_cancelled(document)
            spans.begin_stage(document.id, attempt, current_stage)
            document.parse_status = "completed"
            document.error_message = None
            document.embedding_model_id = kb.embedding_model_id
            document.processed_at = datetime.now(UTC)
            self.documents.save(document)
            spans.end_stage(document.id, attempt, current_stage, output_json={"parse_status": "completed"})
            spans.finalize_root(document.id, attempt, "done")
        except DocumentProcessingCancelled as exc:
            spans.cancel_attempt(document.id, attempt, str(exc))
            document.parse_status = "cancelled"
            document.error_message = str(exc)
            self.documents.save(document)
            raise
        except Exception as exc:
            if current_stage is not None:
                spans.fail_stage(document.id, attempt, current_stage, exc)
            spans.finalize_root(document.id, attempt, "failed", error_message=str(exc))
            document.parse_status = "failed"
            document.error_message = str(exc)
            self.documents.save(document)
            raise

    def _raise_if_cancelled(self, document) -> None:
        self.db.refresh(document)
        if document.parse_status == "cancelled":
            raise DocumentProcessingCancelled(document.error_message or "用户已取消解析")


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
            _apply_chunk_contract(document, chunk)
            db_chunks.append(chunk)
            parent_ids.append(chunk.id)
        embedding_chunks: list[Chunk] = []
        for child in result.children:
            chunk = _to_db_chunk(document, child.chunk, len(db_chunks), "child")
            chunk.parent_chunk_id = parent_ids[child.parent_index]
            _apply_chunk_contract(document, chunk)
            db_chunks.append(chunk)
            embedding_chunks.append(chunk)
        return db_chunks, embedding_chunks

    parsed_chunks = AdaptiveTextChunker(_chunking_config(chunking)).split(text)
    db_chunks = [_to_db_chunk(document, item, item.index, "text") for item in parsed_chunks]
    for chunk in db_chunks:
        _apply_chunk_contract(document, chunk)
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
        tag_id=document.tag_id,
        chunk_metadata=metadata,
        images=item.images or [],
    )


def _apply_chunk_contract(document, chunk: Chunk) -> Chunk:
    metadata = dict(chunk.chunk_metadata or {})
    metadata.update(
        {
            "tenant_id": document.tenant_id,
            "knowledge_base_id": document.knowledge_base_id,
            "document_id": document.id,
            "knowledge_id": document.id,
            "title": document.title,
            "chunk_id": chunk.id,
            "chunk_type": chunk.chunk_type,
            "position": chunk.chunk_index,
            "index": chunk.chunk_index,
            "context_header": chunk.context_header,
            "normalized_content": chunk.search_text or chunk.content,
            "search_text": chunk.search_text or chunk.content,
            "start_at": chunk.start_at,
            "end_at": chunk.end_at,
        }
    )
    if chunk.chunk_type == "child":
        metadata["child_chunk_id"] = chunk.id
        metadata["parent_chunk_id"] = chunk.parent_chunk_id
    else:
        metadata["child_chunk_id"] = None
        metadata["parent_chunk_id"] = chunk.parent_chunk_id
    chunk.chunk_metadata = metadata
    return chunk


def _embedding_content(chunk: Chunk) -> str:
    content = chunk.content.strip()
    return f"{chunk.context_header}\n\n{content}" if chunk.context_header else content


def _search_text(title: str | None, context_header: str | None, content: str) -> str:
    return "\n".join(item for item in (title, context_header, content) if item).strip()
