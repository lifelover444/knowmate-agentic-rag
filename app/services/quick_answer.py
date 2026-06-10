import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import ChatMessage, Knowledge
from app.integrations.llm_openai import OpenAIChatModel
from app.rag.attachments import prepare_attachments
from app.rag.prompt import build_quick_answer_messages
from app.rag.query_rewrite import build_query_rewrite_messages
from app.rag.quick_answer import AnswerResult, AnswerSource
from app.schemas.quick_answer import SourceRead
from app.services.knowledge_search import KnowledgeSearchService
from app.services.model_config import ModelConfigService
from app.services.retrieval_config import RetrievalConfigService


@dataclass
class QuickAnswerPrepared:
    answer: str
    sources: list[AnswerSource]
    source_payloads: list[dict]
    retrieval_trace: dict
    model_config: dict
    rendered_context: str = ""
    prompt_context_summary: str = ""
    attachment_metadata: list[dict] | None = None
    rewritten_query: str | None = None
    messages: list[dict[str, str]] | None = None
    chat_model: object | None = None


class QuickAnswerService:
    def __init__(self, db: Session, settings: Settings, embedder, chat_model, vector_store) -> None:
        self.db = db
        self.settings = settings
        self.embedder = embedder
        self.chat_model = chat_model
        self.vector_store = vector_store

    def answer(
        self,
        knowledge_base_id: str | None,
        query: str,
        top_k: int | None = None,
        enable_rerank: bool | None = None,
        knowledge_base_ids: list[str] | None = None,
        knowledge_ids: list[str] | None = None,
        attachments: list | None = None,
    ):
        prepared = self.prepare_answer(
            knowledge_base_id=knowledge_base_id,
            knowledge_base_ids=knowledge_base_ids,
            knowledge_ids=knowledge_ids,
            query=query,
            top_k=top_k,
            enable_rerank=enable_rerank,
            attachments=attachments,
        )
        return AnswerResult(answer=prepared.answer, sources=prepared.sources)

    def prepare_answer(
        self,
        *,
        knowledge_base_id: str | None,
        knowledge_base_ids: list[str] | None = None,
        knowledge_ids: list[str] | None = None,
        query: str,
        top_k: int | None = None,
        enable_rerank: bool | None = None,
        history: list[ChatMessage] | None = None,
        enable_query_rewrite: bool = True,
        temperature: float | None = None,
        system_prompt: str | None = None,
        generate_answer: bool = True,
        attachments: list | None = None,
    ) -> QuickAnswerPrepared:
        primary_kb_id = knowledge_base_id or _primary_knowledge_base_id(knowledge_base_ids, knowledge_ids, self.db)
        prepared_attachments, attachments_context = prepare_attachments(attachments or [])
        attachment_metadata = [item.metadata() for item in prepared_attachments]
        stages: list[dict] = []
        rewrite_started = time.perf_counter()
        rewritten_query, rewrite_trace = self._rewrite_query(
            knowledge_base_id=primary_kb_id,
            query=query,
            history=history or [],
            enable_query_rewrite=enable_query_rewrite,
            temperature=temperature,
        )
        rewrite_status = "skipped"
        if enable_query_rewrite and not rewrite_trace.get("rewrite_skipped"):
            rewrite_status = "failed" if rewrite_trace.get("rewrite_failed") else "done"
        stages.append(
            _trace_stage(
                "rewrite",
                rewrite_status,
                rewrite_started,
                input={"query": query, "history_count": len(history or [])},
                output={
                    "enabled": enable_query_rewrite,
                    "rewritten_query": rewritten_query,
                    "failed": rewrite_trace.get("rewrite_failed"),
                    "skipped": rewrite_trace.get("rewrite_skipped"),
                },
            )
        )
        search_query = rewritten_query or query
        conversation_context, history_trace = _build_conversation_context(history or [])
        search_result = KnowledgeSearchService(
            self.db,
            self.settings,
            self.embedder,
            self.vector_store,
        ).search_with_diagnostics(
            knowledge_base_id=knowledge_base_id,
            knowledge_base_ids=knowledge_base_ids,
            knowledge_ids=knowledge_ids,
            query=search_query,
            top_k=top_k,
            enable_rerank=enable_rerank,
        )
        hits = search_result.hits
        stages.extend(search_result.diagnostics.get("stages") or [])
        effective_retrieval_mode = search_result.diagnostics.get("mode")
        effective_enable_rerank = search_result.diagnostics.get("enable_rerank")
        model_config = self._model_config_payload(primary_kb_id)
        retrieval_config = RetrievalConfigService(self.db, self.settings).get()
        trace_counts = _retrieval_trace_counts(search_result.diagnostics)
        model_config_used = _trace_model_config_used(model_config, search_result.diagnostics)
        answer_started = time.perf_counter()
        retrieval_trace = {
            **rewrite_trace,
            "query_original": query,
            "query_normalized": search_query,
            "query_rewritten": rewritten_query,
            "retrieval_mode": effective_retrieval_mode,
            "top_k": top_k,
            "enable_rerank": effective_enable_rerank,
            "hit_count": len(hits),
            "vector_hits": trace_counts["vector_hits"],
            "keyword_hits": trace_counts["keyword_hits"],
            "rrf_hits": trace_counts["rrf_hits"],
            "rerank_hits": trace_counts["rerank_hits"],
            "selected_contexts": [],
            "model_config_used": model_config_used,
            "diagnostics": search_result.diagnostics,
            "context_chunk_ids": [hit.chunk_id for hit in hits],
            "context_char_count": 0,
            "context_truncated": False,
            "attachments_used": bool(prepared_attachments),
            "attachments": attachment_metadata,
            "attachments_truncated": any(item.truncated for item in prepared_attachments),
            "attachments_char_count": sum(item.char_count for item in prepared_attachments),
            "prompt_context_summary": "",
            "rendered_context": "",
            **history_trace,
            "stages": stages,
        }
        if not hits and not attachments_context:
            retrieval_trace["stages"].append(
                _trace_stage(
                    "answer",
                    "skipped",
                    answer_started,
                    input={"hit_count": 0},
                    output={"reason": "no_hits"},
                    error_message="没有在知识库中找到可引用的内容。",
                )
            )
            return QuickAnswerPrepared(
                answer="没有在知识库中找到可引用的内容。",
                sources=[],
                source_payloads=[],
                retrieval_trace=retrieval_trace,
                model_config=model_config,
                attachment_metadata=attachment_metadata,
                rewritten_query=rewritten_query,
            )

        sources = [_hit_to_source(hit) for hit in hits]
        context_started = time.perf_counter()
        sources, context_blocks, selected_contexts, selection_truncated = _select_final_contexts(
            sources,
            max_count=retrieval_config.final_context_count,
            max_chars=retrieval_config.max_context_chars,
        )
        retrieval_trace["stages"].append(
            _trace_stage(
                "context_select",
                "done",
                context_started,
                input={
                    "candidate_count": len(hits),
                    "final_context_count": retrieval_config.final_context_count,
                    "max_context_chars": retrieval_config.max_context_chars,
                },
                output={
                    "selected_context_count": len(selected_contexts),
                    "selected_chunk_ids": [item["chunk_id"] for item in selected_contexts],
                    "context_char_count": sum(item["char_count"] for item in selected_contexts),
                    "max_context_chars": retrieval_config.max_context_chars,
                    "truncated": selection_truncated,
                },
            )
        )
        raw_context = "\n\n---\n\n".join(context_blocks)
        combined_context = "\n\n---\n\n".join([part for part in [raw_context, attachments_context] if part])
        rendered_context, context_truncated = _truncate_text(
            combined_context,
            max_chars=retrieval_config.max_context_chars,
        )
        prompt_context_summary = _build_prompt_context_summary(sources, attachment_metadata=attachment_metadata)
        retrieval_trace["selected_contexts"] = selected_contexts
        retrieval_trace["context_chunk_ids"] = [source.chunk_id for source in sources]
        retrieval_trace["context_char_count"] = len(combined_context)
        retrieval_trace["context_truncated"] = context_truncated or selection_truncated
        retrieval_trace["prompt_context_summary"] = prompt_context_summary
        retrieval_trace["rendered_context"] = rendered_context
        chat_model = self._chat_model(primary_kb_id)
        messages = build_quick_answer_messages(
            query=search_query,
            contexts=context_blocks,
            system_prompt=system_prompt,
            conversation_context=conversation_context,
            attachments_context=attachments_context,
        )
        answer = _complete(chat_model, messages, temperature or 0.2) if generate_answer else ""
        retrieval_trace["stages"].append(
            _trace_stage(
                "answer",
                "done" if generate_answer else "pending",
                answer_started,
                input={"context_count": len(sources), "attachment_count": len(prepared_attachments)},
                output={"streaming": not generate_answer},
            )
        )
        source_payloads = [_source_to_read(source).model_dump() for source in sources]
        return QuickAnswerPrepared(
            answer=answer,
            sources=sources,
            source_payloads=source_payloads,
            retrieval_trace=retrieval_trace,
            model_config=model_config,
            rendered_context=rendered_context,
            prompt_context_summary=prompt_context_summary,
            attachment_metadata=attachment_metadata,
            rewritten_query=rewritten_query,
            messages=messages,
            chat_model=chat_model,
        )

    def _rewrite_query(
        self,
        *,
        knowledge_base_id: str,
        query: str,
        history: list[ChatMessage],
        enable_query_rewrite: bool,
        temperature: float | None,
    ) -> tuple[str | None, dict]:
        trace = {
            "original_query": query,
            "rewritten_query": None,
            "rewrite_enabled": enable_query_rewrite,
            "rewrite_failed": False,
            "rewrite_skipped": False,
        }
        if not enable_query_rewrite:
            return None, trace
        user_assistant_history = [
            {"role": message.role, "content": message.content}
            for message in history
            if message.role in {"user", "assistant"} and message.content
        ]
        if not user_assistant_history:
            trace["rewrite_skipped"] = True
            return None, trace
        try:
            rewritten = _complete(
                self._chat_model(knowledge_base_id),
                build_query_rewrite_messages(user_assistant_history, query),
                temperature or 0.2,
            ).strip()
            if rewritten:
                trace["rewritten_query"] = rewritten
                return rewritten, trace
        except Exception:
            trace["rewrite_failed"] = True
        return None, trace

    def _chat_model(self, knowledge_base_id: str):
        if self.chat_model is not None:
            return self.chat_model
        model_service = ModelConfigService(self.db, self.settings)
        from app.db.repositories.knowledge_base import KnowledgeBaseRepository

        kb = KnowledgeBaseRepository(self.db).get(knowledge_base_id, self.settings.default_tenant_id)
        if kb is None:
            raise LookupError("knowledge base not found")
        return OpenAIChatModel(model_service.build_runtime_config_for_model(kb.summary_model_id, "KnowledgeQA"))

    def _model_config_payload(self, knowledge_base_id: str) -> dict:
        from app.db.repositories.knowledge_base import KnowledgeBaseRepository

        kb = KnowledgeBaseRepository(self.db).get(knowledge_base_id, self.settings.default_tenant_id)
        if kb is None:
            return {}
        service = ModelConfigService(self.db, self.settings)
        payload = {
            "knowledge_base_id": knowledge_base_id,
            "embedding_model_id": kb.embedding_model_id,
            "qa_model_id": kb.summary_model_id,
        }
        for key, model_id, expected_type in (
            ("embedding_model", kb.embedding_model_id, "Embedding"),
            ("qa_model", kb.summary_model_id, "KnowledgeQA"),
        ):
            try:
                model = service.get_model(model_id, expected_type)
            except Exception:
                continue
            payload[key] = {
                "id": model.id,
                "name": model.name,
                "type": model.type,
                "provider": model.provider,
                "model_name": model.embedding_model if model.type == "Embedding" else model.chat_model,
            }
        return payload


def _hit_to_source(hit) -> AnswerSource:
    metadata = hit.metadata or {}
    title = hit.title or metadata.get("title") or hit.document_id
    return AnswerSource(
        document_id=hit.document_id,
        knowledge_base_id=hit.knowledge_base_id,
        knowledge_base_name=hit.knowledge_base_name,
        chunk_id=hit.chunk_id,
        content=hit.content,
        score=hit.score,
        document_title=title,
        title=title,
        snippet=_source_snippet_text(hit.context_content or hit.content),
        source_type=str(metadata.get("source_type") or hit.chunk_type or "document"),
        context_header=hit.context_header,
        parent_chunk_id=hit.parent_chunk_id,
        chunk_type=hit.chunk_type,
        metadata=metadata,
        retrieval_method=hit.retrieval_method,
        vector_score=hit.vector_score,
        keyword_score=hit.keyword_score,
        rrf_score=hit.rrf_score,
        rerank_score=hit.rerank_score,
        context_chunk_id=hit.context_chunk_id,
        context_content=hit.context_content,
    )


def _source_to_read(source: AnswerSource) -> SourceRead:
    return SourceRead(
        document_id=source.document_id,
        knowledge_base_id=source.knowledge_base_id,
        knowledge_base_name=source.knowledge_base_name,
        chunk_id=source.chunk_id,
        document_title=source.document_title or source.title,
        title=source.title,
        snippet=source.snippet or _source_snippet(source),
        source_type=source.source_type or _source_type(source),
        content=source.content,
        score=source.score,
        context_header=source.context_header,
        parent_chunk_id=source.parent_chunk_id,
        chunk_type=source.chunk_type,
        metadata=source.metadata,
        retrieval_method=source.retrieval_method,
        vector_score=source.vector_score,
        keyword_score=source.keyword_score,
        rrf_score=source.rrf_score,
        rerank_score=source.rerank_score,
        context_chunk_id=source.context_chunk_id,
        context_content=source.context_content,
    )


def _source_context(source: AnswerSource) -> str:
    body = source.context_content or source.content
    return f"{source.context_header}\n\n{body}" if source.context_header else body


def _select_final_contexts(
    sources: list[AnswerSource],
    *,
    max_count: int,
    max_chars: int,
) -> tuple[list[AnswerSource], list[str], list[dict], bool]:
    selected_sources: list[AnswerSource] = []
    context_blocks: list[str] = []
    selected_contexts: list[dict] = []
    seen_keys: set[str] = set()
    used_chars = 0
    truncated = False
    for source in sources:
        if len(selected_sources) >= max_count:
            break
        context_text = _compress_context_text(_source_context(source))
        if not context_text:
            continue
        dedup_key = source.context_chunk_id or source.parent_chunk_id or source.chunk_id or context_text[:200]
        if dedup_key in seen_keys:
            continue
        next_index = len(selected_sources) + 1
        title = source.document_title or source.title or source.document_id
        parent = f", parent_chunk_id={source.parent_chunk_id}" if source.parent_chunk_id else ""
        header = f"[{next_index}] {title} (document_id={source.document_id}, chunk_id={source.chunk_id}{parent})"
        block = f"{header}\n{context_text}"
        separator_chars = 5 if context_blocks else 0
        remaining = max_chars - used_chars - separator_chars
        if remaining <= 0:
            truncated = True
            break
        block_truncated = False
        if len(block) > remaining:
            block, block_truncated = _truncate_text(block, max_chars=remaining)
            truncated = True
        selected_source = _with_source_preview(source)
        selected_sources.append(selected_source)
        context_blocks.append(block)
        seen_keys.add(dedup_key)
        used_chars += len(block) + separator_chars
        selected_contexts.append(
            {
                "index": next_index,
                "document_id": selected_source.document_id,
                "document_title": selected_source.document_title or selected_source.title,
                "chunk_id": selected_source.chunk_id,
                "parent_chunk_id": selected_source.parent_chunk_id,
                "context_chunk_id": selected_source.context_chunk_id,
                "source_type": selected_source.source_type or _source_type(selected_source),
                "score": selected_source.score,
                "rerank_score": selected_source.rerank_score,
                "char_count": len(block),
                "truncated": block_truncated,
                "snippet": selected_source.snippet or _source_snippet(selected_source),
            }
        )
    return selected_sources, context_blocks, selected_contexts, truncated


def _with_source_preview(source: AnswerSource) -> AnswerSource:
    from dataclasses import replace

    return replace(
        source,
        document_title=source.document_title or source.title,
        snippet=source.snippet or _source_snippet(source),
        source_type=source.source_type or _source_type(source),
    )


def _compress_context_text(value: str) -> str:
    lines = [line.rstrip() for line in (value or "").strip().splitlines()]
    compact: list[str] = []
    blank = False
    for line in lines:
        if not line.strip():
            if not blank:
                compact.append("")
            blank = True
            continue
        compact.append(line)
        blank = False
    return "\n".join(compact).strip()


def _source_type(source: AnswerSource) -> str:
    metadata = source.metadata or {}
    return str(metadata.get("source_type") or source.chunk_type or "document")


def _source_snippet(source: AnswerSource, *, max_chars: int = 240) -> str:
    return _source_snippet_text(source.context_content or source.content, max_chars=max_chars)


def _source_snippet_text(value: str, *, max_chars: int = 240) -> str:
    text = " ".join((value or "").split())
    return text[:max_chars]


def _build_prompt_context_summary(
    sources: list[AnswerSource],
    *,
    attachment_metadata: list[dict] | None = None,
    max_chars: int = 1200,
) -> str:
    lines: list[str] = []
    for index, source in enumerate(sources, start=1):
        text = " ".join((source.context_content or source.content or "").split())
        preview = text[:180]
        title = source.title or source.document_id
        lines.append(f"{index}. {title} / {source.chunk_id}: {preview}")
    for attachment in attachment_metadata or []:
        truncated = "，已截断" if attachment.get("truncated") else ""
        lines.append(f"附件: {attachment.get('filename')} ({attachment.get('file_type')}{truncated})")
    summary = "\n".join(lines)
    truncated, _ = _truncate_text(summary, max_chars=max_chars)
    return truncated


def _build_conversation_context(
    history: list[ChatMessage],
    *,
    max_messages: int = 6,
    max_chars: int = 1600,
) -> tuple[str, dict]:
    eligible = [
        message
        for message in history
        if message.role in {"user", "assistant"} and message.content and message.status != "failed"
    ]
    selected = eligible[-max_messages:]
    candidate_lines: list[str] = []
    for message in selected:
        role = "User" if message.role == "user" else "Assistant"
        content = " ".join(message.content.split())
        if content:
            candidate_lines.append(f"{role}: {content}")
    raw_context = "\n".join(candidate_lines)
    kept_reversed: list[str] = []
    used_chars = 0
    truncated = False
    for line in reversed(candidate_lines):
        separator_chars = 1 if kept_reversed else 0
        remaining = max_chars - used_chars - separator_chars
        if remaining <= 0:
            truncated = True
            break
        if len(line) > remaining:
            kept_reversed.append(line[: max(0, remaining - 8)].rstrip() + "…")
            truncated = True
            break
        kept_reversed.append(line)
        used_chars += len(line) + separator_chars
    if len(kept_reversed) < len(candidate_lines):
        truncated = True
    conversation_context = "\n".join(reversed(kept_reversed))
    return conversation_context, {
        "history_used": bool(conversation_context),
        "history_message_count": len(selected),
        "history_char_count": len(raw_context),
        "history_truncated": truncated,
    }


def _truncate_text(value: str, *, max_chars: int) -> tuple[str, bool]:
    text = value or ""
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars].rstrip() + "\n...[已截断]", True


def _retrieval_trace_counts(diagnostics: dict) -> dict[str, int]:
    stages = {stage.get("name"): stage for stage in diagnostics.get("stages") or []}
    return {
        "vector_hits": _summary_number((stages.get("vector") or {}).get("output", {}).get("hit_count")),
        "keyword_hits": _summary_number((stages.get("keyword") or {}).get("output", {}).get("hit_count")),
        "rrf_hits": _summary_number((stages.get("rrf") or {}).get("output", {}).get("output_count")),
        "rerank_hits": _summary_number((stages.get("rerank") or {}).get("output", {}).get("rerank_output_count")),
    }


def _summary_number(value) -> int:
    if isinstance(value, list):
        return sum(_summary_number(item) for item in value)
    if isinstance(value, int | float):
        return int(value)
    return 0


def _trace_model_config_used(model_config: dict, diagnostics: dict) -> dict:
    payload = {
        "knowledge_base_id": model_config.get("knowledge_base_id"),
        "embedding_model_id": model_config.get("embedding_model_id"),
        "qa_model_id": model_config.get("qa_model_id"),
    }
    rerank_model_id = None
    for stage in diagnostics.get("stages") or []:
        if stage.get("name") == "rerank":
            model_used = (stage.get("output") or {}).get("model_config_used")
            if model_used and model_used != "injected":
                rerank_model_id = model_used
            break
    payload["rerank_model_id"] = rerank_model_id
    return payload


def _complete(chat_model, messages: list[dict[str, str]], temperature: float) -> str:
    try:
        return chat_model.complete(messages, temperature=temperature)
    except TypeError:
        return chat_model.complete(messages)


def stream_complete(chat_model, messages: list[dict[str, str]], temperature: float):
    if hasattr(chat_model, "stream_complete"):
        try:
            yield from chat_model.stream_complete(messages, temperature=temperature)
            return
        except TypeError:
            yield from chat_model.stream_complete(messages)
            return
    yield _complete(chat_model, messages, temperature)


def _primary_knowledge_base_id(
    knowledge_base_ids: list[str] | None,
    knowledge_ids: list[str] | None,
    db: Session,
) -> str:
    if knowledge_base_ids:
        return knowledge_base_ids[0]
    if knowledge_ids:
        document = db.get(Knowledge, knowledge_ids[0])
        if document is not None:
            return document.knowledge_base_id
    raise ValueError("至少提供一个 knowledge_base_id、knowledge_base_ids 或 knowledge_ids")


def _trace_stage(
    name: str,
    status: str,
    started_at: float | None,
    *,
    input: dict | None = None,
    output: dict | None = None,
    error_message: str | None = None,
) -> dict:
    duration_ms = 0 if started_at is None else max(0, int((time.perf_counter() - started_at) * 1000))
    return {
        "name": name,
        "status": status,
        "duration_ms": duration_ms,
        "input": input or {},
        "output": output or {},
        "error_message": error_message,
    }
