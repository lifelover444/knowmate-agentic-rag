from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_settings
from app.core.config import Settings
from app.db.repositories.vector_store import VectorStoreRepository
from app.integrations.qdrant_store import QdrantVectorStore
from app.schemas.vector_store import (
    VectorStoreCreate,
    VectorStoreRead,
    VectorStoreTestRequest,
    VectorStoreTestResponse,
    VectorStoreTypeRead,
    VectorStoreUpdate,
)
from app.services.vector_store import VectorStoreService, to_safe_vector_store

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("", response_model=list[VectorStoreRead])
def list_vector_stores(db: DBSession, settings: AppSettings):
    return [to_safe_vector_store(item) for item in VectorStoreRepository(db).list(settings.default_tenant_id)]


@router.post("", response_model=VectorStoreRead, status_code=status.HTTP_201_CREATED)
def create_vector_store(payload: VectorStoreCreate, db: DBSession, settings: AppSettings):
    try:
        store = VectorStoreService(VectorStoreRepository(db), settings).create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_safe_vector_store(store)


@router.get("/types", response_model=list[VectorStoreTypeRead])
def list_vector_store_types(db: DBSession, settings: AppSettings):
    return VectorStoreService(VectorStoreRepository(db), settings).list_types()


@router.post("/test", response_model=VectorStoreTestResponse)
def test_vector_store(payload: VectorStoreTestRequest, db: DBSession, settings: AppSettings, request: Request):
    dry_run = not isinstance(request.app.state.vector_store, QdrantVectorStore)
    try:
        ok, message = VectorStoreService(VectorStoreRepository(db), settings).test_connection(
            payload.provider,
            payload.config_json,
            dry_run=dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return VectorStoreTestResponse(ok=ok, message=message)


@router.get("/{store_id}", response_model=VectorStoreRead)
def get_vector_store(store_id: str, db: DBSession, settings: AppSettings):
    store = VectorStoreRepository(db).get(store_id, settings.default_tenant_id)
    if store is None:
        raise HTTPException(status_code=404, detail="VectorStore 不存在")
    return to_safe_vector_store(store)


@router.put("/{store_id}", response_model=VectorStoreRead)
def update_vector_store(store_id: str, payload: VectorStoreUpdate, db: DBSession, settings: AppSettings):
    repo = VectorStoreRepository(db)
    store = repo.get(store_id, settings.default_tenant_id)
    if store is None:
        raise HTTPException(status_code=404, detail="VectorStore 不存在")
    try:
        updated = VectorStoreService(repo, settings).update(store, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_safe_vector_store(updated)


@router.delete("/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vector_store(store_id: str, db: DBSession, settings: AppSettings):
    repo = VectorStoreRepository(db)
    store = repo.get(store_id, settings.default_tenant_id)
    if store is None:
        raise HTTPException(status_code=404, detail="VectorStore 不存在")
    try:
        VectorStoreService(repo, settings).delete(store)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return None
