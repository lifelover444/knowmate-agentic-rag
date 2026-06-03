import os
import time
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_settings
from app.core.config import Settings
from app.db.repositories.model_config import ModelConfigRepository
from app.db.repositories.vector_store import VectorStoreRepository
from app.integrations.vector_store import mask_vector_store_config
from app.rag.parser import ParserEngineRegistry
from app.services.vector_store import VectorStoreService, to_safe_vector_store

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("")
def get_runtime_status(request: Request, db: DBSession, settings: AppSettings):
    database = _database_status(db)
    storage = _storage_status(settings)
    storage_providers = _storage_provider_status(storage)
    vector_store = _vector_store_status(request.app.state.vector_store)
    vector_stores = _vector_stores_status(db, settings)
    model_configs = _model_config_status(db, settings)
    parser_engines = _parser_engine_status()
    fix_suggestions = _fix_suggestions(
        database=database,
        storage=storage,
        vector_store=vector_store,
        parser_engines=parser_engines,
        model_configs=model_configs,
    )
    system_ok = all(
        item["status"] == "ok"
        for item in [database, storage, vector_store]
    ) and any(engine["status"] == "ok" for engine in parser_engines)
    return {
        "system": {"status": "ok" if system_ok else "degraded"},
        "database": database,
        "storage": storage,
        "storage_providers": storage_providers,
        "vector_store": vector_store,
        "vector_stores": vector_stores,
        "model_configs": model_configs,
        "parser_engines": parser_engines,
        "fix_suggestions": fix_suggestions,
    }


def _database_status(db: Session) -> dict:
    started_at = time.perf_counter()
    try:
        db.execute(text("select 1"))
        return {
            "provider": db.bind.dialect.name if db.bind is not None else "unknown",
            "status": "ok",
            "latency_ms": _duration_ms(started_at),
            "checked_at": _now_iso(),
        }
    except Exception as exc:
        return {
            "provider": "unknown",
            "status": "error",
            "latency_ms": _duration_ms(started_at),
            "checked_at": _now_iso(),
            "error_message": f"数据库连接失败：{exc}",
        }


def _storage_status(settings: Settings) -> dict:
    try:
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        writable = os.access(settings.upload_dir, os.W_OK)
        return {
            "provider": "local",
            "status": "ok" if writable else "error",
            "path": str(settings.upload_dir),
            "writable": writable,
            "error_message": None if writable else "上传目录不可写",
            "fix_suggestion": None if writable else "请检查上传目录权限或调整 UPLOAD_DIR",
        }
    except Exception as exc:
        return {
            "provider": "local",
            "status": "error",
            "path": str(settings.upload_dir),
            "writable": False,
            "error_message": f"本地存储不可用：{exc}",
            "fix_suggestion": "请检查上传目录路径和权限，或调整 UPLOAD_DIR",
        }


def _storage_provider_status(local_status: dict) -> list[dict]:
    return [
        {
            "provider": "local",
            "label": "Local Storage",
            "status": local_status["status"],
            "available": local_status["status"] == "ok",
            "description": "开发环境使用本地上传目录保存原始文件。",
            "path": local_status.get("path"),
            "fix_suggestion": local_status.get("fix_suggestion"),
        },
        *_planned_storage_providers(),
    ]


def _planned_storage_providers() -> list[dict]:
    return [
        {
            "provider": provider,
            "label": label,
            "status": "planned",
            "available": False,
            "description": f"{label} 对象存储 provider 暂未启用。",
            "fix_suggestion": "当前 Quick Q&A v1 使用 local storage；接入对象存储需新增 provider 配置。",
        }
        for provider, label in [
            ("minio", "MinIO"),
            ("s3", "S3"),
            ("oss", "OSS"),
            ("cos", "COS"),
            ("obs", "OBS"),
        ]
    ]


def _vector_store_status(vector_store) -> dict:
    started_at = time.perf_counter()
    try:
        if hasattr(vector_store, "test_connection"):
            vector_store.test_connection()
        return {
            "provider": vector_store.__class__.__name__,
            "status": "ok",
            "latency_ms": _duration_ms(started_at),
            "checked_at": _now_iso(),
        }
    except Exception as exc:
        return {
            "provider": vector_store.__class__.__name__,
            "status": "error",
            "latency_ms": _duration_ms(started_at),
            "checked_at": _now_iso(),
            "error_message": f"向量库连接失败：{exc}",
            "fix_suggestion": "请检查 Qdrant 服务、端口、TLS 和 API Key 配置。",
        }


def _vector_stores_status(db: Session, settings: Settings) -> dict:
    stores = VectorStoreRepository(db).list(settings.default_tenant_id)
    items = [to_safe_vector_store(store) for store in stores]
    default = next((item for item in items if item.get("is_default")), None)
    if default is None:
        registry = VectorStoreService(VectorStoreRepository(db), settings).registry
        default = {
            "id": None,
            "tenant_id": settings.default_tenant_id,
            "name": "默认 Qdrant",
            "provider": "qdrant",
            "status": "active",
            "is_default": True,
            "config_json": mask_vector_store_config(registry.default_config()),
        }
    return {
        "registered_count": max(len(items), 1),
        "items": items or [default],
        "default": default,
        "fix_suggestion": None if default.get("provider") == "qdrant" else "当前 Quick Q&A 默认仅启用 Qdrant。",
    }


def _model_config_status(db: Session, settings: Settings) -> dict:
    models = ModelConfigRepository(db).list(settings.default_tenant_id)
    required_types = {}
    for model_type in ["KnowledgeQA", "Embedding", "Rerank"]:
        candidates = [model for model in models if model.type == model_type and model.status == "active"]
        selected = candidates[0] if candidates else None
        required_types[model_type] = {
            "status": "ok" if selected else "missing",
            "count": len(candidates),
            "active_model_id": selected.id if selected else None,
            "provider": selected.provider if selected else None,
            "model_name": _runtime_model_name(selected, model_type),
            "api_key_configured": bool(selected.api_key_encrypted) if selected else False,
            "api_key_last4": selected.api_key_last4 if selected else None,
            "fix_suggestion": None if selected else f"请在模型配置中新增可用的 {model_type} 模型。",
        }
    return {
        "summary": {
            "total": len(models),
            "active": sum(1 for model in models if model.status == "active"),
            "api_key_configured": sum(1 for model in models if bool(model.api_key_encrypted)),
        },
        "required_types": required_types,
        "items": [
            {
                "id": model.id,
                "type": model.type,
                "provider": model.provider,
                "name": model.name,
                "status": model.status,
                "api_key_configured": bool(model.api_key_encrypted),
                "api_key_last4": model.api_key_last4,
                "model_name": model.chat_model if model.type != "Embedding" else model.embedding_model,
            }
            for model in models
        ],
    }


def _runtime_model_name(model, model_type: str) -> str | None:
    if model is None:
        return None
    if model_type == "Embedding":
        return model.embedding_model
    return model.chat_model


def _parser_engine_status() -> list[dict]:
    engines = ParserEngineRegistry().list_engines()
    items = [
        {
            **engine,
            "status": "ok" if engine["available"] else "planned",
            "error_message": engine.get("unavailable_reason") or None,
            "fix_suggestion": None
            if engine["available"]
            else f"{engine['name']} parser 暂未接入；当前请使用 builtin parser 或接入对应外部服务。",
        }
        for engine in engines
    ]
    known = {item["name"] for item in items}
    for name, label, file_types in [
        ("mineru", "MinerU OCR / Advanced Parser", ["pdf", "jpg", "jpeg", "png"]),
        ("docreader", "DocReader", ["pdf", "docx", "pptx"]),
    ]:
        if name not in known:
            items.append(
                {
                    "name": name,
                    "label": label,
                    "description": f"{label} provider 暂未启用。",
                    "file_types": file_types,
                    "available": False,
                    "status": "planned",
                    "error_message": f"{label} 尚未配置",
                    "fix_suggestion": f"接入 {label} 后可在 parser engine registry 中启用。",
                }
            )
    return items


def _fix_suggestions(
    *,
    database: dict,
    storage: dict,
    vector_store: dict,
    parser_engines: list[dict],
    model_configs: dict,
) -> list[str]:
    suggestions: list[str] = []
    for name, item in [("数据库", database), ("本地存储", storage), ("向量库", vector_store)]:
        if item.get("status") != "ok":
            suggestions.append(str(item.get("fix_suggestion") or f"请检查{name}配置。"))
    for model_type, item in (model_configs.get("required_types") or {}).items():
        if item.get("status") != "ok":
            suggestions.append(str(item.get("fix_suggestion") or f"请配置 {model_type} 模型。"))
    if not any(engine.get("status") == "ok" for engine in parser_engines):
        suggestions.append("请至少启用一个 parser engine。")
    return suggestions


def _duration_ms(started_at: float) -> int:
    return max(0, int((time.perf_counter() - started_at) * 1000))


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
