from fastapi import APIRouter

from app.api.v1 import (
    chunker,
    documents,
    knowledge_bases,
    knowledge_search,
    model_config,
    models,
    parser_engines,
    quick_answer,
    retrieval_config,
)

api_router = APIRouter()
api_router.include_router(knowledge_bases.router, prefix="/knowledge-bases", tags=["knowledge-bases"])
api_router.include_router(knowledge_search.router, prefix="/knowledge-search", tags=["knowledge-search"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(quick_answer.router, prefix="/quick-answer", tags=["quick-answer"])
api_router.include_router(model_config.router, prefix="/model-config", tags=["model-config"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(retrieval_config.router, prefix="/retrieval-config", tags=["retrieval-config"])
api_router.include_router(chunker.router, prefix="/chunker", tags=["chunker"])
api_router.include_router(parser_engines.router, prefix="/parser-engines", tags=["parser-engines"])
