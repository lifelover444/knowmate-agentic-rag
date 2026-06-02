import os
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_settings
from app.core.config import Settings
from app.rag.parser import ParserEngineRegistry

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("")
def get_runtime_status(request: Request, db: DBSession, settings: AppSettings):
    database = _database_status(db)
    storage = _storage_status(settings)
    vector_store = _vector_store_status(request.app.state.vector_store)
    parser_engines = _parser_engine_status()
    system_ok = all(
        item["status"] == "ok"
        for item in [database, storage, vector_store]
    ) and any(engine["status"] == "ok" for engine in parser_engines)
    return {
        "system": {"status": "ok" if system_ok else "degraded"},
        "database": database,
        "storage": storage,
        "vector_store": vector_store,
        "parser_engines": parser_engines,
    }


def _database_status(db: Session) -> dict:
    try:
        db.execute(text("select 1"))
        return {"provider": db.bind.dialect.name if db.bind is not None else "unknown", "status": "ok"}
    except Exception as exc:
        return {"provider": "unknown", "status": "error", "error_message": f"数据库连接失败：{exc}"}


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
        }
    except Exception as exc:
        return {
            "provider": "local",
            "status": "error",
            "path": str(settings.upload_dir),
            "writable": False,
            "error_message": f"本地存储不可用：{exc}",
        }


def _vector_store_status(vector_store) -> dict:
    try:
        if hasattr(vector_store, "test_connection"):
            vector_store.test_connection()
        return {"provider": vector_store.__class__.__name__, "status": "ok"}
    except Exception as exc:
        return {
            "provider": vector_store.__class__.__name__,
            "status": "error",
            "error_message": f"向量库连接失败：{exc}",
        }


def _parser_engine_status() -> list[dict]:
    engines = ParserEngineRegistry().list_engines()
    return [
        {
            **engine,
            "status": "ok" if engine["available"] else "unavailable",
            "error_message": engine.get("unavailable_reason") or None,
        }
        for engine in engines
    ]
