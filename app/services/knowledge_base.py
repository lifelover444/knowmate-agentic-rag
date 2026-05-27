from app.core.config import Settings
from app.db.models import KnowledgeBase
from app.db.repositories.document import DocumentRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate
from app.services.model_config import MODEL_CONFIG_REQUIRED_MESSAGE, ModelConfigService


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
        model_service = ModelConfigService(self.repo.db, self.settings)
        embedding_model_id = payload.embedding_model_id
        summary_model_id = payload.summary_model_id
        if not embedding_model_id or not summary_model_id:
            raise ValueError(MODEL_CONFIG_REQUIRED_MESSAGE)
        model_service.get_model(embedding_model_id, "Embedding")
        model_service.get_model(summary_model_id, "KnowledgeQA")
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
                embedding_model_id=embedding_model_id,
                summary_model_id=summary_model_id,
            )
        )

    def update(self, kb: KnowledgeBase, payload: KnowledgeBaseUpdate) -> KnowledgeBase:
        model_service = ModelConfigService(self.repo.db, self.settings)
        data = payload.model_dump(exclude_unset=True)

        if "embedding_model_id" in data and data["embedding_model_id"]:
            model_service.get_model(data["embedding_model_id"], "Embedding")
            kb.embedding_model_id = data["embedding_model_id"]
        if "summary_model_id" in data and data["summary_model_id"]:
            model_service.get_model(data["summary_model_id"], "KnowledgeQA")
            kb.summary_model_id = data["summary_model_id"]
        if "name" in data and data["name"] is not None:
            kb.name = data["name"]
        if "description" in data:
            kb.description = data["description"]
        if "chunking_config" in data and data["chunking_config"] is not None:
            kb.chunking_config = normalize_chunking_config(data["chunking_config"], self.settings)
        if "parser_engine_rules" in data and data["parser_engine_rules"] is not None:
            kb.parser_engine_rules = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in data["parser_engine_rules"]
            ]
        return self.repo.save(kb)

    def soft_delete(self, kb: KnowledgeBase, vector_store=None) -> KnowledgeBase:
        documents = DocumentRepository(self.repo.db).soft_delete_by_knowledge_base(kb.id)
        if vector_store is not None and hasattr(vector_store, "delete_by_knowledge_id"):
            for document in documents:
                vector_store.delete_by_knowledge_id(document.id)
        return self.repo.soft_delete(kb)
