import json
import time
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.deps import get_chat_model, get_db, get_embedder, get_settings, get_vector_store
from app.core.config import Settings
from app.db.repositories.chat import ChatRepository
from app.schemas.chat import ChatSessionCreate
from app.schemas.quick_answer import QuickAnswerRequest, QuickAnswerResponse, QuickAnswerStreamRequest, SourceRead
from app.services.chat import ChatService, to_chat_message_read, to_chat_session_read
from app.services.quick_answer import QuickAnswerService, stream_complete

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
EmbedderDep = Annotated[object, Depends(get_embedder)]
ChatModelDep = Annotated[object, Depends(get_chat_model)]
VectorStoreDep = Annotated[object, Depends(get_vector_store)]


@router.post("", response_model=QuickAnswerResponse)
def quick_answer(
    payload: QuickAnswerRequest,
    db: DBSession,
    settings: AppSettings,
    embedder: EmbedderDep,
    chat_model: ChatModelDep,
    vector_store: VectorStoreDep,
):
    try:
        prepared = QuickAnswerService(db, settings, embedder, chat_model, vector_store).prepare_answer(
            knowledge_base_id=payload.knowledge_base_id,
            knowledge_base_ids=payload.knowledge_base_ids,
            knowledge_ids=payload.knowledge_ids,
            query=payload.query,
            top_k=payload.top_k,
            enable_rerank=payload.enable_rerank,
            attachments=payload.attachments,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QuickAnswerResponse(
        answer=prepared.answer,
        sources=[
            SourceRead(
                document_id=source.document_id,
                knowledge_base_id=source.knowledge_base_id,
                knowledge_base_name=source.knowledge_base_name,
                chunk_id=source.chunk_id,
                document_title=source.document_title or source.title,
                title=source.title,
                snippet=source.snippet,
                source_type=source.source_type,
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
            for source in prepared.sources
        ],
        retrieval_trace=prepared.retrieval_trace,
    )


@router.post("/stream")
def quick_answer_stream(
    payload: QuickAnswerStreamRequest,
    request: Request,
    db: DBSession,
    settings: AppSettings,
    embedder: EmbedderDep,
    chat_model: ChatModelDep,
    vector_store: VectorStoreDep,
):
    try:
        repo = ChatRepository(db)
        chat_service = ChatService(repo, settings)
        if payload.session_id:
            session = repo.get_session(payload.session_id, settings.default_tenant_id)
            if session is None:
                raise LookupError("chat session not found")
        else:
            primary_kb_id = payload.knowledge_base_id or (
                payload.knowledge_base_ids[0] if payload.knowledge_base_ids else None
            )
            if primary_kb_id is None:
                raise ValueError("至少提供一个 knowledge_base_id、knowledge_base_ids 或 knowledge_ids")
            session = chat_service.create_session(
                ChatSessionCreate(
                    knowledge_base_id=primary_kb_id,
                    title=payload.query[:40],
                )
            )
        if payload.knowledge_base_id and session.knowledge_base_id != payload.knowledge_base_id:
            raise ValueError("会话绑定的知识库与请求不一致")
        history = repo.list_messages(session.id, settings.default_tenant_id)
        session = chat_service.maybe_auto_title(session, payload.query, len(history))
        attachment_metadata: list[dict] = []
        prepared = QuickAnswerService(db, settings, embedder, chat_model, vector_store).prepare_answer(
            knowledge_base_id=payload.knowledge_base_id,
            knowledge_base_ids=payload.knowledge_base_ids,
            knowledge_ids=payload.knowledge_ids,
            query=payload.query,
            top_k=payload.top_k,
            enable_rerank=payload.enable_rerank,
            history=history,
            enable_query_rewrite=True,
            temperature=payload.temperature,
            system_prompt=payload.system_prompt,
            generate_answer=False,
            attachments=payload.attachments,
        )
        attachment_metadata = prepared.attachment_metadata or []
        user_message = chat_service.create_user_message(
            session,
            payload.query,
            payload.mentioned_items,
            attachments=attachment_metadata,
        )
        started_at = time.perf_counter()
        base_state = _last_request_state(
            payload=payload,
            prepared=prepared,
            status="running",
            started_at=started_at,
            duration_ms=0,
        )
        session = chat_service.update_last_request_state(session, base_state)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    def event_stream():
        answer_parts: list[str] = []
        generation_id = str(uuid4())
        registry = request.app.state.chat_stop_registry
        registry.register(session.id, generation_id)
        if hasattr(prepared.chat_model, "registry"):
            prepared.chat_model.registry = registry
        try:
            yield _sse("session", to_chat_session_read(session).model_dump(mode="json"))
            yield _sse("user_message", {"id": user_message.id})
            yield _sse(
                "rewrite",
                {
                    "original_query": payload.query,
                    "rewritten_query": prepared.rewritten_query,
                    "enabled": bool(payload.enable_query_rewrite),
                    "failed": bool(prepared.retrieval_trace.get("rewrite_failed")),
                    "skipped": bool(prepared.retrieval_trace.get("rewrite_skipped")),
                },
            )
            yield _sse(
                "retrieval",
                {
                    "id": session.id,
                    "hit_count": len(prepared.source_payloads),
                    "sources": prepared.source_payloads,
                    "retrieval_trace": prepared.retrieval_trace,
                },
            )
            try:
                if prepared.chat_model is None or prepared.messages is None:
                    token_iterable = prepared.answer or "没有在知识库中找到可引用的内容。"
                else:
                    token_iterable = stream_complete(prepared.chat_model, prepared.messages, payload.temperature or 0.2)
                for token in token_iterable:
                    stopped, reason = registry.is_stopped(session.id, generation_id)
                    if stopped:
                        answer = "".join(answer_parts)
                        _set_trace_stage(prepared.retrieval_trace, "answer", "cancelled", error_message=reason)
                        assistant_message = chat_service.create_assistant_message(
                            session,
                            content=answer,
                            original_query=payload.query,
                            rewritten_query=prepared.rewritten_query,
                            sources=prepared.source_payloads,
                            retrieval_trace={**prepared.retrieval_trace, "stream_cancelled": True},
                            model_config=prepared.model_config,
                            rendered_context=prepared.rendered_context,
                            prompt_context_summary=prepared.prompt_context_summary,
                            status="cancelled",
                            error_message=reason or "用户已停止生成",
                        )
                        chat_service.update_last_request_state(
                            session,
                            _last_request_state(
                                payload=payload,
                                prepared=prepared,
                                status="cancelled",
                                started_at=started_at,
                                duration_ms=_duration_ms(started_at),
                                error_message=assistant_message.error_message,
                            ),
                        )
                        yield _sse(
                            "stopped",
                            {
                                "assistant_message": to_chat_message_read(assistant_message).model_dump(mode="json"),
                                "answer": answer,
                                "error_message": assistant_message.error_message,
                            },
                        )
                        yield _sse("done", {})
                        return
                    answer_parts.append(token)
                    yield _sse("token", {"text": token})
                answer = "".join(answer_parts)
                _set_trace_stage(prepared.retrieval_trace, "answer", "done")
                assistant_message = chat_service.create_assistant_message(
                    session,
                    content=answer,
                    original_query=payload.query,
                    rewritten_query=prepared.rewritten_query,
                    sources=prepared.source_payloads,
                    retrieval_trace=prepared.retrieval_trace,
                    model_config=prepared.model_config,
                    rendered_context=prepared.rendered_context,
                    prompt_context_summary=prepared.prompt_context_summary,
                )
            except Exception as exc:
                error_message = f"回答生成失败：{exc}"
                _set_trace_stage(prepared.retrieval_trace, "answer", "failed", error_message=error_message)
                chat_service.create_assistant_message(
                    session,
                    content="",
                    original_query=payload.query,
                    rewritten_query=prepared.rewritten_query,
                    sources=prepared.source_payloads,
                    retrieval_trace={**prepared.retrieval_trace, "stream_failed": True},
                    model_config=prepared.model_config,
                    rendered_context=prepared.rendered_context,
                    prompt_context_summary=prepared.prompt_context_summary,
                    status="failed",
                    error_message=error_message,
                )
                chat_service.update_last_request_state(
                    session,
                    _last_request_state(
                        payload=payload,
                        prepared=prepared,
                        status="failed",
                        started_at=started_at,
                        duration_ms=_duration_ms(started_at),
                        error_message=error_message,
                    ),
                )
                yield _sse("error", {"error": error_message})
                yield _sse("done", {})
                return
            chat_service.update_last_request_state(
                session,
                _last_request_state(
                    payload=payload,
                    prepared=prepared,
                    status="completed",
                    started_at=started_at,
                    duration_ms=_duration_ms(started_at),
                ),
            )
            yield _sse(
                "final",
                {
                    "assistant_message": to_chat_message_read(assistant_message).model_dump(mode="json"),
                    "answer": answer,
                    "sources": prepared.source_payloads,
                    "retrieval_trace": prepared.retrieval_trace,
                },
            )
            yield _sse("done", {})
        finally:
            registry.unregister(session.id, generation_id)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _duration_ms(started_at: float) -> int:
    return max(0, int((time.perf_counter() - started_at) * 1000))


def _last_request_state(
    *,
    payload: QuickAnswerStreamRequest,
    prepared,
    status: str,
    started_at: float,
    duration_ms: int,
    error_message: str | None = None,
) -> dict:
    return {
        "status": status,
        "query": payload.query,
        "knowledge_base_id": payload.knowledge_base_id,
        "knowledge_base_ids": payload.knowledge_base_ids,
        "knowledge_ids": payload.knowledge_ids,
        "mentioned_items": payload.mentioned_items,
        "attachments": prepared.attachment_metadata or [],
        "attachments_used": bool(prepared.attachment_metadata),
        "attachments_truncated": any(item.get("truncated") for item in (prepared.attachment_metadata or [])),
        "top_k": payload.top_k,
        "mode": "hybrid",
        "enable_rerank": payload.enable_rerank,
        "enable_query_rewrite": bool(payload.enable_query_rewrite),
        "temperature": payload.temperature,
        "system_prompt": payload.system_prompt,
        "hit_count": len(prepared.source_payloads),
        "model_config": prepared.model_config,
        "started_at": started_at,
        "duration_ms": duration_ms,
        "error_message": error_message,
    }


def _set_trace_stage(trace: dict, name: str, status: str, error_message: str | None = None) -> None:
    for stage in trace.get("stages") or []:
        if stage.get("name") == name:
            stage["status"] = status
            if error_message:
                stage["error_message"] = error_message
            return
