from fastapi import APIRouter

from app.api.v1 import chunker, documents, knowledge_bases, model_config, parser_engines, quick_answer

api_router = APIRouter()
api_router.include_router(knowledge_bases.router, prefix="/knowledge-bases", tags=["knowledge-bases"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(quick_answer.router, prefix="/quick-answer", tags=["quick-answer"])
api_router.include_router(model_config.router, prefix="/model-config", tags=["model-config"])
api_router.include_router(chunker.router, prefix="/chunker", tags=["chunker"])
api_router.include_router(parser_engines.router, prefix="/parser-engines", tags=["parser-engines"])
