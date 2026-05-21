from fastapi import APIRouter

from app.api.v1 import documents, knowledge_bases, quick_answer

api_router = APIRouter()
api_router.include_router(knowledge_bases.router, prefix="/knowledge-bases", tags=["knowledge-bases"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(quick_answer.router, prefix="/quick-answer", tags=["quick-answer"])
