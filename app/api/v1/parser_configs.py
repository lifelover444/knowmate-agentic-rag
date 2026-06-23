from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_settings
from app.core.config import Settings
from app.schemas.parser_config import (
    ParserConfigPayload,
    ParserConfigRead,
    ParserCredentialPayload,
    ParserCredentialsRead,
)
from app.services.parser_config import ParserProviderConfigService

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("", response_model=list[ParserConfigRead])
def list_parser_configs(db: DBSession, settings: AppSettings):
    return ParserProviderConfigService(db, settings).list_configs()


@router.get("/{provider}", response_model=ParserConfigRead)
def get_parser_config(provider: str, db: DBSession, settings: AppSettings):
    try:
        return ParserProviderConfigService(db, settings).get_read(provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{provider}", response_model=ParserConfigRead)
def save_parser_config(provider: str, payload: ParserConfigPayload, db: DBSession, settings: AppSettings):
    try:
        return ParserProviderConfigService(db, settings).save(provider, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{provider}/credentials", response_model=ParserCredentialsRead)
def update_parser_credentials(
    provider: str,
    payload: ParserCredentialPayload,
    db: DBSession,
    settings: AppSettings,
):
    try:
        return ParserProviderConfigService(db, settings).update_credentials(provider, payload.api_key)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{provider}/credentials/{field}", status_code=status.HTTP_204_NO_CONTENT)
def clear_parser_credential(provider: str, field: str, db: DBSession, settings: AppSettings):
    try:
        ParserProviderConfigService(db, settings).clear_credential(provider, field)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
