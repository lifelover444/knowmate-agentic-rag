import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import ChatMessage, Knowledge
from app.integrations.llm_openai import OpenAIChatModel
from app.rag.prompt import build_quick_answer_messages
from app.rag.query_rewrite import build_query_rewrite_messages
from app.rag.quick_answer import AnswerResult, AnswerSource
from app.schemas.quick_answer import SourceRead
from app.services.knowledge_search import KnowledgeSearchService
from app.services.model_config import ModelConfigService


@dataclass
class QuickAnswerPrepared:
    answer: str
    sources: list[AnswerSource]
    source_payloads: list[dict]
    retrieval_trace: dict
    model_config: dict
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
        mode: str | None = None,
        enable_rerank: bool | None = None,
        knowledge_base_ids: list[str] | None = None,
        knowledge_ids: list[str] | None = None,
    ):
        prepared = self.prepare_answer(
            knowledge_base_id=knowledge_base_id,
            knowledge_base_ids=knowledge_base_ids,
            knowledge_ids=knowledge_ids,
            query=query,
            top_k=top_k,
            mode=mode,
            enable_rerank=enable_rerank,
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
        mode: str | None = None,
        enable_rerank: bool | None = None,
        history: list[ChatMessage] | None = None,
        enable_query_rewrite: bool = False,
        temperature: float | None = None,
        system_prompt: str | None = None,
        generate_answer: bool = True,
    ) -> QuickAnswerPrepared:
        primary_kb_id = knowledge_base_id or _primary_knowledge_base_id(knowledge_base_ids, knowledge_ids, self.db)
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
                output={
                    "enabled": enable_query_rewrite,
                    "rewritten_query": rewritten_query,
                    "failed": rewrite_trace.get("rewrite_failed"),
                    "skipped": rewrite_trace.get("rewrite_skipped"),
                },
            )
        )
        search_query = rewritten_query or query
        search_started = time.perf_counter()
        hits = KnowledgeSearchService(self.db, self.settings, self.embedder, self.vector_store).search(
            knowledge_base_id=knowledge_base_id,
            knowledge_base_ids=knowledge_base_ids,
            knowledge_ids=knowledge_ids,
            query=search_query,
            mode=mode,
            top_k=top_k,
            enable_rerank=enable_rerank,
        )
        stages.append(
            _trace_stage(
                "search",
                "done",
                search_started,
                output={"hit_count": len(hits), "mode": mode, "top_k": top_k},
            )
        )
        model_config = self._model_config_payload(primary_kb_id)
        should_rerank = bool(enable_rerank)
        stages.append(
            _trace_stage(
                "rerank",
                "done" if should_rerank else "skipped",
                None,
                output={"enabled": should_rerank},
            )
        )
        answer_started = time.perf_counter()
        retrieval_trace = {
            **rewrite_trace,
            "retrieval_mode": mode,
            "top_k": top_k,
            "enable_rerank": enable_rerank,
            "hit_count": len(hits),
            "stages": stages,
        }
        if not hits:
            retrieval_trace["stages"].append(
                _trace_stage("answer", "skipped", answer_started, output={"reason": "no_hits"})
            )
            return QuickAnswerPrepared(
                answer="没有在知识库中找到可引用的内容。",
                sources=[],
                source_payloads=[],
                retrieval_trace=retrieval_trace,
                model_config=model_config,
                rewritten_query=rewritten_query,
            )

        sources = [_hit_to_source(hit) for hit in hits]
        chat_model = self._chat_model(primary_kb_id)
        messages = build_quick_answer_messages(
            query=search_query,
            contexts=[
                f"{source.context_header}\n\n{source.context_content or source.content}"
                if source.context_header
                else source.context_content or source.content
                for source in sources
            ],
            system_prompt=system_prompt,
        )
        answer = _complete(chat_model, messages, temperature or 0.2) if generate_answer else ""
        retrieval_trace["stages"].append(
            _trace_stage(
                "answer",
                "done" if generate_answer else "pending",
                answer_started,
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
    return AnswerSource(
        document_id=hit.document_id,
        knowledge_base_id=hit.knowledge_base_id,
        knowledge_base_name=hit.knowledge_base_name,
        chunk_id=hit.chunk_id,
        content=hit.content,
        score=hit.score,
        title=hit.title,
        context_header=hit.context_header,
        parent_chunk_id=hit.parent_chunk_id,
        chunk_type=hit.chunk_type,
        metadata=hit.metadata or {},
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
        title=source.title,
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
    output: dict | None = None,
    error_message: str | None = None,
) -> dict:
    duration_ms = 0 if started_at is None else max(0, int((time.perf_counter() - started_at) * 1000))
    return {
        "name": name,
        "status": status,
        "duration_ms": duration_ms,
        "output": output or {},
        "error_message": error_message,
    }
