from app.core.config import Settings
from app.db.models import KnowledgeBase
from app.db.repositories.chunk import ChunkRepository
from app.db.repositories.document import DocumentRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.db.repositories.vector_store import VectorStoreRepository
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate
from app.services.model_config import MODEL_CONFIG_REQUIRED_MESSAGE, ModelConfigService


def default_chunking_config(settings: Settings) -> dict:
    return {
        "chunk_size": 512,
        "chunk_overlap": 80,
        "separators": ["\n\n", "\n", "。"],
        "strategy": "auto",
        "token_limit": 0,
        "languages": [],
        "enable_parent_child": True,
        "parent_chunk_size": 4096,
        "child_chunk_size": 384,
    }


def normalize_chunking_config(config: dict | None, settings: Settings) -> dict:
    normalized = default_chunking_config(settings)
    if config:
        normalized.update(config)
    normalized["chunk_size"] = 512
    normalized["chunk_overlap"] = 80
    normalized["separators"] = ["\n\n", "\n", "。"]
    normalized["token_limit"] = 0
    normalized["enable_parent_child"] = True
    normalized["parent_chunk_size"] = 4096
    normalized["child_chunk_size"] = 384
    normalized["strategy"] = "auto"
    return normalized


def default_parser_engine_rules() -> list[dict]:
    return [
        {
            "file_types": [
                "pdf",
                "doc",
                "docx",
                "ppt",
                "pptx",
                "xls",
                "xlsx",
                "png",
                "jpg",
                "jpeg",
                "jp2",
                "webp",
                "gif",
                "bmp",
            ],
            "engine": "mineru",
        },
        {"file_types": ["md", "markdown"], "engine": "builtin"},
        {"file_types": ["txt"], "engine": "builtin"},
        {"file_types": ["csv", "json"], "engine": "builtin"},
    ]


def default_indexing_strategy() -> dict:
    return {
        "enable_vector": True,
        "enable_keyword": True,
        "enable_parent_child": True,
        "enable_rerank": True,
        "enable_wiki": False,
        "enable_knowledge_graph": False,
    }


def normalize_indexing_strategy(strategy: dict | None) -> dict:
    normalized = default_indexing_strategy()
    if strategy:
        normalized.update({key: bool(value) for key, value in strategy.items() if key in normalized})
    normalized["enable_vector"] = True
    normalized["enable_keyword"] = True
    normalized["enable_parent_child"] = True
    normalized["enable_rerank"] = True
    normalized["enable_wiki"] = False
    normalized["enable_knowledge_graph"] = False
    return normalized


def default_faq_config() -> dict:
    return {
        "index_mode": "question_answer",
        "question_index_mode": "combined",
    }


def normalize_faq_config(kb_type: str | None, config: dict | None) -> dict | None:
    if normalize_kb_type(kb_type) != "faq":
        return None
    normalized = default_faq_config()
    if config:
        normalized.update(config)
    if normalized["index_mode"] not in {"question_only", "question_answer"}:
        raise ValueError("FAQ index_mode 仅支持 question_only 或 question_answer")
    if normalized["question_index_mode"] not in {"combined", "separate"}:
        raise ValueError("FAQ question_index_mode 仅支持 combined 或 separate")
    return normalized


def knowledge_base_capabilities(kb_type: str | None, indexing_strategy: dict | None) -> dict:
    strategy = normalize_indexing_strategy(indexing_strategy)
    normalized_type = normalize_kb_type(kb_type)
    return {
        "document": normalized_type == "document",
        "faq": normalized_type == "faq",
        "vector": bool(strategy["enable_vector"]),
        "keyword": bool(strategy["enable_keyword"]),
        "parent_child": bool(strategy["enable_parent_child"]),
        "rerank": bool(strategy["enable_rerank"]),
        "wiki": False,
        "graph": False,
    }


def normalize_kb_type(value: str | None) -> str:
    kb_type = (value or "document").strip().lower()
    if kb_type not in {"document", "faq"}:
        raise ValueError("知识库类型仅支持 document 或 faq")
    return kb_type


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
        vector_store_id = payload.vector_store_id
        if vector_store_id:
            vector_store = VectorStoreRepository(self.repo.db).get(vector_store_id, self.settings.default_tenant_id)
            if vector_store is None or vector_store.status != "active":
                raise ValueError("VectorStore 不存在或不可用")
        chunking = payload.chunking_config or {}
        if hasattr(chunking, "model_dump"):
            chunking = chunking.model_dump()
        chunking = normalize_chunking_config(chunking, self.settings)
        indexing_strategy = payload.indexing_strategy or {}
        if hasattr(indexing_strategy, "model_dump"):
            indexing_strategy = indexing_strategy.model_dump()
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
                kb_type=normalize_kb_type(payload.kb_type),
                chunking_config=chunking,
                parser_engine_rules=parser_engine_rules,
                faq_config=normalize_faq_config(payload.kb_type, _dump_model(payload.faq_config)),
                indexing_strategy=normalize_indexing_strategy(indexing_strategy),
                vector_store_id=vector_store_id,
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
        if "kb_type" in data and data["kb_type"] is not None:
            kb.kb_type = normalize_kb_type(data["kb_type"])
            kb.faq_config = normalize_faq_config(kb.kb_type, kb.faq_config)
        if "chunking_config" in data and data["chunking_config"] is not None:
            kb.chunking_config = normalize_chunking_config(data["chunking_config"], self.settings)
        if "parser_engine_rules" in data and data["parser_engine_rules"] is not None:
            kb.parser_engine_rules = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in data["parser_engine_rules"]
            ]
        if "faq_config" in data:
            kb.faq_config = normalize_faq_config(kb.kb_type, _dump_model(data["faq_config"]))
        if "indexing_strategy" in data and data["indexing_strategy"] is not None:
            kb.indexing_strategy = normalize_indexing_strategy(data["indexing_strategy"])
        if "vector_store_id" in data:
            vector_store_id = data["vector_store_id"]
            if vector_store_id:
                vector_store = VectorStoreRepository(self.repo.db).get(vector_store_id, self.settings.default_tenant_id)
                if vector_store is None or vector_store.status != "active":
                    raise ValueError("VectorStore 不存在或不可用")
            kb.vector_store_id = vector_store_id
        return self.repo.save(kb)

    def soft_delete(self, kb: KnowledgeBase, vector_store=None) -> KnowledgeBase:
        documents = DocumentRepository(self.repo.db).soft_delete_by_knowledge_base(kb.id)
        chunk_repo = ChunkRepository(self.repo.db)
        if vector_store is not None and hasattr(vector_store, "delete_by_knowledge_id"):
            for document in documents:
                chunk_repo.bm25_delete_by_document(document.id)
                vector_store.delete_by_knowledge_id(document.id)
        else:
            for document in documents:
                chunk_repo.bm25_delete_by_document(document.id)
        return self.repo.soft_delete(kb)


def _dump_model(value):
    if value is None:
        return None
    return value.model_dump() if hasattr(value, "model_dump") else value
