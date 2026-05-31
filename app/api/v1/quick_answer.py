import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
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
        result = QuickAnswerService(db, settings, embedder, chat_model, vector_store).answer(
            knowledge_base_id=payload.knowledge_base_id,
            query=payload.query,
            top_k=payload.top_k,
            mode=payload.mode,
            enable_rerank=payload.enable_rerank,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QuickAnswerResponse(
        answer=result.answer,
        sources=[
            SourceRead(
                document_id=source.document_id,
                knowledge_base_id=source.knowledge_base_id,
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
            for source in result.sources
        ],
    )


@router.post("/stream")
def quick_answer_stream(
    payload: QuickAnswerStreamRequest,
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
            session = chat_service.create_session(
                ChatSessionCreate(
                    knowledge_base_id=payload.knowledge_base_id,
                    title=payload.query[:40],
                )
            )
        if session.knowledge_base_id != payload.knowledge_base_id:
            raise ValueError("会话绑定的知识库与请求不一致")
        history = repo.list_messages(session.id, settings.default_tenant_id)
        user_message = chat_service.create_user_message(session, payload.query)
        prepared = QuickAnswerService(db, settings, embedder, chat_model, vector_store).prepare_answer(
            knowledge_base_id=payload.knowledge_base_id,
            query=payload.query,
            top_k=payload.top_k,
            mode=payload.mode,
            enable_rerank=payload.enable_rerank,
            history=history,
            enable_query_rewrite=bool(payload.enable_query_rewrite),
            temperature=payload.temperature,
            system_prompt=payload.system_prompt,
            generate_answer=False,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    def event_stream():
        answer_parts: list[str] = []
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
                "hit_count": len(prepared.source_payloads),
                "sources": prepared.source_payloads,
                "retrieval_trace": prepared.retrieval_trace,
            },
        )
        try:
            if prepared.chat_model is None or prepared.messages is None:
                for token in prepared.answer or "没有在知识库中找到可引用的内容。":
                    answer_parts.append(token)
                    yield _sse("token", {"text": token})
            else:
                for token in stream_complete(prepared.chat_model, prepared.messages, payload.temperature or 0.2):
                    answer_parts.append(token)
                    yield _sse("token", {"text": token})
            answer = "".join(answer_parts)
            assistant_message = chat_service.create_assistant_message(
                session,
                content=answer,
                original_query=payload.query,
                rewritten_query=prepared.rewritten_query,
                sources=prepared.source_payloads,
                retrieval_trace=prepared.retrieval_trace,
                model_config=prepared.model_config,
            )
        except Exception as exc:
            error_message = f"回答生成失败：{exc}"
            chat_service.create_assistant_message(
                session,
                content="",
                original_query=payload.query,
                rewritten_query=prepared.rewritten_query,
                sources=prepared.source_payloads,
                retrieval_trace={**prepared.retrieval_trace, "stream_failed": True},
                model_config=prepared.model_config,
                status="failed",
                error_message=error_message,
            )
            yield _sse("error", {"error": error_message})
            yield _sse("done", {})
            return
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

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
