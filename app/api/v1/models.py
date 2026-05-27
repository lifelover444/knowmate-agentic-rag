from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_settings
from app.core.config import Settings
from app.schemas.models import (
    ModelCreate,
    ModelCredentialPayload,
    ModelCredentialsRead,
    ModelRead,
    ModelTestPayload,
    ModelUpdate,
)
from app.services.model_config import ModelConfigService

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def service(db: Session, settings: Settings, request: Request) -> ModelConfigService:
    return ModelConfigService(db, settings, tester=request.app.state.model_tester)


@router.get("", response_model=list[ModelRead])
def list_models(db: DBSession, settings: AppSettings, request: Request, type: str | None = None):
    return service(db, settings, request).list_models(type)


@router.post("", response_model=ModelRead, status_code=status.HTTP_201_CREATED)
def create_model(payload: ModelCreate, db: DBSession, settings: AppSettings, request: Request):
    try:
        return service(db, settings, request).create_model(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{model_id}", response_model=ModelRead)
def get_model(model_id: str, db: DBSession, settings: AppSettings, request: Request):
    try:
        return service(db, settings, request).get_model_read(model_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{model_id}", response_model=ModelRead)
def update_model(model_id: str, payload: ModelUpdate, db: DBSession, settings: AppSettings, request: Request):
    try:
        return service(db, settings, request).update_model(model_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(model_id: str, db: DBSession, settings: AppSettings, request: Request):
    try:
        service(db, settings, request).delete_model(model_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/test")
def test_model(payload: ModelTestPayload, db: DBSession, settings: AppSettings, request: Request):
    try:
        return service(db, settings, request).test_model(payload)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{model_id}/credentials", response_model=ModelCredentialsRead)
def update_credentials(
    model_id: str,
    payload: ModelCredentialPayload,
    db: DBSession,
    settings: AppSettings,
    request: Request,
):
    try:
        return service(db, settings, request).update_credentials(model_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{model_id}/credentials/{field}", status_code=status.HTTP_204_NO_CONTENT)
def clear_credential(model_id: str, field: str, db: DBSession, settings: AppSettings, request: Request):
    try:
        service(db, settings, request).clear_credential(model_id, field)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
