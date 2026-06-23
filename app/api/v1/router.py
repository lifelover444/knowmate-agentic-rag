from fastapi import APIRouter

from app.api.v1 import (
    chat_sessions,
    chunker,
    chunks,
    documents,
    faqs,
    knowledge_bases,
    knowledge_search,
    messages,
    model_config,
    models,
    parser_configs,
    parser_engines,
    quick_answer,
    retrieval_config,
    runtime_status,
    tags,
    tasks,
    vector_stores,
)

api_router = APIRouter()
api_router.include_router(chat_sessions.router, prefix="/chat-sessions", tags=["chat-sessions"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(knowledge_bases.router, prefix="/knowledge-bases", tags=["knowledge-bases"])
api_router.include_router(tags.router, prefix="/knowledge-bases", tags=["tags"])
api_router.include_router(faqs.router, prefix="/knowledge-bases/{kb_id}/faqs", tags=["faqs"])
api_router.include_router(knowledge_search.router, prefix="/knowledge-search", tags=["knowledge-search"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(chunks.router, prefix="/chunks", tags=["chunks"])
api_router.include_router(quick_answer.router, prefix="/quick-answer", tags=["quick-answer"])
api_router.include_router(model_config.router, prefix="/model-config", tags=["model-config"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(parser_configs.router, prefix="/parser-configs", tags=["parser-configs"])
api_router.include_router(retrieval_config.router, prefix="/retrieval-config", tags=["retrieval-config"])
api_router.include_router(runtime_status.router, prefix="/runtime-status", tags=["runtime-status"])
api_router.include_router(chunker.router, prefix="/chunker", tags=["chunker"])
api_router.include_router(parser_engines.router, prefix="/parser-engines", tags=["parser-engines"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(vector_stores.router, prefix="/vector-stores", tags=["vector-stores"])
