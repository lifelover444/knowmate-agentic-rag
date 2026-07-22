import uuid
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Chunk
from app.db.repositories.chunk import ChunkRepository
from app.db.repositories.document import DocumentRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.integrations.llm_openai import OpenAIEmbedder
from app.integrations.mineru import MinerUClient, MinerUConfig, MinerUError, MinerUParseResult
from app.integrations.pdf_splitter import PdfSplitError, get_pdf_page_count, split_pdf_by_page_limit
from app.rag.chunker import AdaptiveTextChunker, ChunkingConfig, ParsedChunk, split_parent_child
from app.rag.legal_structure import build_legal_search_text, extract_legal_metadata
from app.rag.parser import DocumentParser, ParsedDocument
from app.services.knowledge_base import normalize_chunking_config
from app.services.model_config import ModelConfigService
from app.services.parser_config import MINERU_PROVIDER, ParserProviderConfigService
from app.services.processing_spans import ProcessingSpanService


class DocumentProcessingCancelled(RuntimeError):
    pass


class DocumentProcessingService:
    def __init__(
        self,
        db: Session,
        upload_dir: Path,
        vector_store,
        settings=None,
        embedder=None,
        generated_question_generator=None,
    ) -> None:
        self.db = db
        self.upload_dir = upload_dir
        self.embedder = embedder
        self.vector_store = vector_store
        self.generated_question_generator = generated_question_generator
        self.settings = settings or Settings()
        self.documents = DocumentRepository(db)
        self.knowledge_bases = KnowledgeBaseRepository(db)
        self.chunks = ChunkRepository(db)

    def process(self, document_id: str) -> None:
        document = self.documents.get(document_id)
        if document is None:
            raise LookupError("document not found")
        if document.parse_status == "cancelled":
            raise DocumentProcessingCancelled(document.error_message or "用户已取消解析")
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
            selected_engine = _select_parser_engine(kb.parser_engine_rules, document.file_type)
            parsed = self._parse_document(
                file_path,
                selected_engine,
                cancel_check=lambda: self._raise_if_cancelled(document),
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
            _apply_generated_questions(
                document=document,
                chunks=embedding_chunks,
                generator=self.generated_question_generator,
            )
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
            self.db.refresh(document)
            if document.parse_status == "cancelled":
                cancellation = DocumentProcessingCancelled(document.error_message or "用户已取消解析")
                spans.cancel_attempt(document.id, attempt, str(cancellation))
                raise cancellation from exc
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

    def _parse_document(self, file_path: Path, engine: str | None, *, cancel_check=None) -> ParsedDocument:
        if engine != MINERU_PROVIDER:
            return DocumentParser().parse(file_path, engine=engine)

        runtime = ParserProviderConfigService(self.db, self.settings).runtime_config(MINERU_PROVIDER)
        client = MinerUClient(
            MinerUConfig(
                base_url=runtime.base_url,
                api_key=runtime.api_key,
                model_version=str(runtime.config.get("model_version") or "vlm"),
                language=str(runtime.config.get("language") or "ch"),
                enable_table=bool(runtime.config.get("enable_table", True)),
                enable_formula=bool(runtime.config.get("enable_formula", True)),
                is_ocr=bool(runtime.config.get("is_ocr", False)),
                poll_interval_seconds=float(runtime.config.get("poll_interval_seconds") or 3),
                poll_timeout_seconds=float(runtime.config.get("poll_timeout_seconds") or 600),
            ),
            cancel_check=cancel_check,
        )
        max_pages_per_part = _mineru_max_pages_per_part(runtime.config.get("max_pages_per_part"))
        return _parse_with_mineru(file_path, client, max_pages_per_part=max_pages_per_part)


def _parse_with_mineru(file_path: Path, client: MinerUClient, *, max_pages_per_part: int) -> ParsedDocument:
    file_type = file_path.suffix.lower().lstrip(".")
    if file_type != "pdf":
        result = client.parse_file(file_path)
        return _mineru_result_to_parsed_document(file_path, result)

    try:
        page_count = get_pdf_page_count(file_path)
    except PdfSplitError as exc:
        raise ValueError(str(exc)) from exc

    if page_count <= max_pages_per_part:
        result = client.parse_file(file_path)
        metadata = {
            "file_name": file_path.name,
            "file_type": file_type,
            **result.metadata,
            "page_count": page_count,
        }
        pages = [{"page": index + 1, "start": 0, "end": 0} for index in range(page_count)]
        return ParsedDocument(title=file_path.name, content=result.markdown, metadata=metadata, pages=pages)

    with TemporaryDirectory(prefix="mineru_pdf_parts_") as temp_dir:
        try:
            parts = split_pdf_by_page_limit(file_path, Path(temp_dir), max_pages=max_pages_per_part)
        except PdfSplitError as exc:
            raise ValueError(str(exc)) from exc

        sections: list[str] = []
        part_metadata: list[dict] = []
        pages: list[dict] = []
        for part in parts:
            try:
                result = client.parse_file(part.path)
            except DocumentProcessingCancelled:
                raise
            except Exception as exc:
                raise MinerUError(
                    f"MinerU 分片 {part.index}/{len(parts)}（第 {part.page_start}-{part.page_end} 页）解析失败：{exc}"
                ) from exc
            markdown = result.markdown.strip()
            section_title = f"## 第 {part.page_start}-{part.page_end} 页"
            sections.append(f"{section_title}\n\n{markdown}" if markdown else section_title)
            part_metadata.append(_mineru_part_metadata(part, result))
            pages.append({"part_index": part.index, "page_start": part.page_start, "page_end": part.page_end})

    metadata = {
        "file_name": file_path.name,
        "file_type": file_type,
        "parser": "mineru",
        "mineru_split": True,
        "mineru_split_part_count": len(part_metadata),
        "mineru_split_max_pages": max_pages_per_part,
        "page_count": page_count,
        "mineru_parts": part_metadata,
    }
    first_part = part_metadata[0] if part_metadata else {}
    if first_part.get("model_version"):
        metadata["model_version"] = first_part["model_version"]
    return ParsedDocument(title=file_path.name, content="\n\n".join(sections).strip(), metadata=metadata, pages=pages)


def _select_parser_engine(rules: list | None, file_type: str | None) -> str | None:
    normalized = (file_type or "").lower().lstrip(".")
    for rule in rules or []:
        if normalized in {item.lower().lstrip(".") for item in rule.get("file_types", [])}:
            return rule.get("engine")
    return "builtin"


def _mineru_max_pages_per_part(raw_value) -> int:
    try:
        value = int(raw_value or 200)
    except (TypeError, ValueError):
        value = 200
    return min(max(value, 1), 200)


def _mineru_result_to_parsed_document(file_path: Path, result: MinerUParseResult) -> ParsedDocument:
    metadata = {
        "file_name": file_path.name,
        "file_type": file_path.suffix.lower().lstrip("."),
        **result.metadata,
    }
    return ParsedDocument(title=file_path.name, content=result.markdown, metadata=metadata)


def _mineru_part_metadata(part, result: MinerUParseResult) -> dict:
    return {
        "part_index": part.index,
        "page_start": part.page_start,
        "page_end": part.page_end,
        "file_name": part.path.name,
        "mineru_batch_id": result.metadata.get("mineru_batch_id"),
        "mineru_state": result.metadata.get("mineru_state"),
        "mineru_trace_id": result.metadata.get("mineru_trace_id"),
        "full_zip_url": result.metadata.get("full_zip_url"),
        "model_version": result.metadata.get("model_version"),
    }


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
    metadata.update(extract_legal_metadata(document.title, item.context_header, item.content))
    search_text = _search_text(document.title, item.context_header, item.content, metadata=metadata)
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


def _apply_generated_questions(document, chunks: list[Chunk], generator) -> None:
    if generator is None:
        return
    for chunk in chunks:
        questions = _normalize_generated_questions(_call_generated_question_generator(generator, chunk))
        if not questions:
            continue
        metadata = dict(chunk.chunk_metadata or {})
        metadata["generated_questions"] = questions
        chunk.chunk_metadata = metadata
        chunk.search_text = _search_text(
            document.title,
            chunk.context_header,
            chunk.content,
            generated_questions=questions,
            metadata=metadata,
        )
        _apply_chunk_contract(document, chunk)


def _call_generated_question_generator(generator, chunk: Chunk):
    if hasattr(generator, "generate"):
        return generator.generate(chunk)
    return generator(chunk)


def _normalize_generated_questions(raw_questions) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in raw_questions or []:
        if isinstance(raw, dict):
            question = str(raw.get("question") or raw.get("content") or "").strip()
            question_id = str(raw.get("id") or uuid.uuid4())
        else:
            question = str(raw or "").strip()
            question_id = str(uuid.uuid4())
        if not question or question in seen:
            continue
        seen.add(question)
        questions.append({"id": question_id, "question": question})
    return questions


def _search_text(
    title: str | None,
    context_header: str | None,
    content: str,
    *,
    generated_questions: list[dict[str, str]] | None = None,
    metadata: dict | None = None,
) -> str:
    return build_legal_search_text(
        title,
        context_header,
        content,
        metadata=metadata,
        generated_questions=generated_questions,
    )
