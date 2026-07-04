from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_settings
from app.core.config import Settings
from app.schemas.evaluation import (
    EvaluationCreate,
    EvaluationRunDetail,
    EvaluationRunRead,
    EvaluationTestsetCreate,
    EvaluationTestsetDetail,
    EvaluationTestsetRead,
)
from app.services.evaluation import EvaluationService
from app.workers import tasks as worker_tasks

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.post("", response_model=EvaluationRunRead, status_code=status.HTTP_202_ACCEPTED)
def create_evaluation(payload: EvaluationCreate, db: DBSession, settings: AppSettings):
    try:
        run = EvaluationService(db, settings).create_run(
            knowledge_base_id=payload.knowledge_base_id,
            testset_size=payload.testset_size,
            top_k=payload.top_k,
            enable_rerank=payload.enable_rerank,
            testset_id=payload.testset_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    worker_tasks.enqueue_evaluation_run(run.id)
    return EvaluationService(db, settings).to_run_read(run)


@router.get("", response_model=list[EvaluationRunRead])
def list_evaluations(
    db: DBSession,
    settings: AppSettings,
    knowledge_base_id: str | None = None,
):
    return EvaluationService(db, settings).list_runs(knowledge_base_id)


@router.post("/testsets", response_model=EvaluationTestsetDetail, status_code=status.HTTP_201_CREATED)
def create_testset(payload: EvaluationTestsetCreate, db: DBSession, settings: AppSettings):
    try:
        return EvaluationService(db, settings).create_testset(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/testsets", response_model=list[EvaluationTestsetRead])
def list_testsets(
    db: DBSession,
    settings: AppSettings,
    knowledge_base_id: str | None = None,
):
    return EvaluationService(db, settings).list_testsets(knowledge_base_id)


@router.get("/testsets/{testset_id}", response_model=EvaluationTestsetDetail)
def get_testset(testset_id: str, db: DBSession, settings: AppSettings):
    detail = EvaluationService(db, settings).get_testset_detail(testset_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="黄金测试集不存在")
    return detail


@router.post("/{run_id}/baseline", response_model=EvaluationRunRead)
def mark_baseline(run_id: str, db: DBSession, settings: AppSettings):
    try:
        run = EvaluationService(db, settings).set_baseline(run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EvaluationService(db, settings).to_run_read(run)


@router.get("/{run_id}", response_model=EvaluationRunDetail)
def get_evaluation(run_id: str, db: DBSession, settings: AppSettings):
    detail = EvaluationService(db, settings).get_run_detail(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="评测任务不存在")
    return detail
