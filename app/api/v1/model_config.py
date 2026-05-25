from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_settings
from app.core.config import Settings
from app.schemas.model_config import ModelConfigPayload, ModelConfigRead, ModelConfigTestResult
from app.services.model_config import ModelConfigService

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def service(db: Session, settings: Settings, request: Request) -> ModelConfigService:
    return ModelConfigService(db, settings, tester=request.app.state.model_tester)


@router.get("", response_model=ModelConfigRead | None)
def get_model_config(db: DBSession, settings: AppSettings, request: Request):
    return service(db, settings, request).read_active()


@router.put("", response_model=ModelConfigRead)
def save_model_config(payload: ModelConfigPayload, db: DBSession, settings: AppSettings, request: Request):
    try:
        return service(db, settings, request).save(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/test", response_model=ModelConfigTestResult)
def test_model_config(
    db: DBSession,
    settings: AppSettings,
    request: Request,
    payload: Annotated[ModelConfigPayload | None, Body()] = None,
):
    try:
        return service(db, settings, request).test(payload)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
