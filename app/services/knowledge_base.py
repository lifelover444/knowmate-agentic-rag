from app.core.config import Settings
from app.db.models import KnowledgeBase
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.schemas.knowledge_base import KnowledgeBaseCreate


def default_chunking_config(settings: Settings) -> dict:
    return {
        "chunk_size": settings.default_chunk_size,
        "chunk_overlap": settings.default_chunk_overlap,
        "separators": ["\n\n", "\n", "。"],
        "strategy": "auto",
        "token_limit": 0,
        "languages": [],
        "enable_parent_child": False,
        "parent_chunk_size": 4096,
        "child_chunk_size": 384,
    }


def normalize_chunking_config(config: dict | None, settings: Settings) -> dict:
    normalized = default_chunking_config(settings)
    if config:
        normalized.update(config)
    return normalized


def default_parser_engine_rules() -> list[dict]:
    return [
        {"file_types": ["pdf"], "engine": "builtin"},
        {"file_types": ["docx"], "engine": "builtin"},
        {"file_types": ["md", "markdown"], "engine": "builtin"},
        {"file_types": ["txt"], "engine": "builtin"},
        {"file_types": ["csv", "json", "xlsx"], "engine": "builtin"},
    ]


class KnowledgeBaseService:
    def __init__(self, repo: KnowledgeBaseRepository, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings

    def create(self, payload: KnowledgeBaseCreate) -> KnowledgeBase:
        chunking = payload.chunking_config or {}
        if hasattr(chunking, "model_dump"):
            chunking = chunking.model_dump()
        chunking = normalize_chunking_config(chunking, self.settings)
        parser_engine_rules = payload.parser_engine_rules or default_parser_engine_rules()
        if hasattr(parser_engine_rules, "model_dump"):
            parser_engine_rules = parser_engine_rules.model_dump()
        parser_engine_rules = [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in parser_engine_rules
        ]
        return self.repo.create(
            KnowledgeBase(
                tenant_id=self.settings.default_tenant_id,
                name=payload.name,
                description=payload.description,
                chunking_config=chunking,
                parser_engine_rules=parser_engine_rules,
                embedding_model_id=self.settings.embedding_model,
                summary_model_id=self.settings.chat_model,
            )
        )
