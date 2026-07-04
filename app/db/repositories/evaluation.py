from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.db.models import EvaluationRun, EvaluationSample, EvaluationTestset, EvaluationTestsetItem


class EvaluationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_run(self, run: EvaluationRun) -> EvaluationRun:
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def save_run(self, run: EvaluationRun) -> EvaluationRun:
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def get_run(self, run_id: str, tenant_id: int) -> EvaluationRun | None:
        return self.db.scalar(
            select(EvaluationRun).where(EvaluationRun.id == run_id, EvaluationRun.tenant_id == tenant_id)
        )

    def get_baseline_run(self, tenant_id: int, knowledge_base_id: str) -> EvaluationRun | None:
        return self.db.scalar(
            select(EvaluationRun)
            .where(
                EvaluationRun.tenant_id == tenant_id,
                EvaluationRun.knowledge_base_id == knowledge_base_id,
                EvaluationRun.is_baseline.is_(True),
            )
            .order_by(EvaluationRun.updated_at.desc(), EvaluationRun.created_at.desc())
            .limit(1)
        )

    def list_runs(self, tenant_id: int, knowledge_base_id: str | None = None) -> list[EvaluationRun]:
        statement = select(EvaluationRun).where(EvaluationRun.tenant_id == tenant_id)
        if knowledge_base_id:
            statement = statement.where(EvaluationRun.knowledge_base_id == knowledge_base_id)
        return list(self.db.scalars(statement.order_by(EvaluationRun.created_at.desc())).all())

    def set_baseline(self, run: EvaluationRun) -> EvaluationRun:
        self.db.execute(
            update(EvaluationRun)
            .where(
                EvaluationRun.tenant_id == run.tenant_id,
                EvaluationRun.knowledge_base_id == run.knowledge_base_id,
                EvaluationRun.id != run.id,
            )
            .values(is_baseline=False)
        )
        run.is_baseline = True
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def add_sample(self, sample: EvaluationSample) -> EvaluationSample:
        self.db.add(sample)
        self.db.commit()
        self.db.refresh(sample)
        return sample

    def delete_samples(self, run_id: str, tenant_id: int) -> None:
        self.db.execute(
            delete(EvaluationSample).where(
                EvaluationSample.evaluation_run_id == run_id,
                EvaluationSample.tenant_id == tenant_id,
            )
        )
        self.db.commit()

    def save_sample(self, sample: EvaluationSample) -> EvaluationSample:
        self.db.add(sample)
        self.db.commit()
        self.db.refresh(sample)
        return sample

    def list_samples(self, run_id: str, tenant_id: int) -> list[EvaluationSample]:
        return list(
            self.db.scalars(
                select(EvaluationSample)
                .where(EvaluationSample.evaluation_run_id == run_id, EvaluationSample.tenant_id == tenant_id)
                .order_by(EvaluationSample.sample_index.asc())
            ).all()
        )

    def create_testset(self, testset: EvaluationTestset) -> EvaluationTestset:
        self.db.add(testset)
        self.db.commit()
        self.db.refresh(testset)
        return testset

    def save_testset(self, testset: EvaluationTestset) -> EvaluationTestset:
        self.db.add(testset)
        self.db.commit()
        self.db.refresh(testset)
        return testset

    def get_testset(self, testset_id: str, tenant_id: int) -> EvaluationTestset | None:
        return self.db.scalar(
            select(EvaluationTestset).where(
                EvaluationTestset.id == testset_id,
                EvaluationTestset.tenant_id == tenant_id,
            )
        )

    def list_testsets(self, tenant_id: int, knowledge_base_id: str | None = None) -> list[EvaluationTestset]:
        statement = select(EvaluationTestset).where(EvaluationTestset.tenant_id == tenant_id)
        if knowledge_base_id:
            statement = statement.where(EvaluationTestset.knowledge_base_id == knowledge_base_id)
        return list(self.db.scalars(statement.order_by(EvaluationTestset.created_at.desc())).all())

    def add_testset_item(self, item: EvaluationTestsetItem) -> EvaluationTestsetItem:
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def list_testset_items(self, testset_id: str, tenant_id: int) -> list[EvaluationTestsetItem]:
        return list(
            self.db.scalars(
                select(EvaluationTestsetItem)
                .where(
                    EvaluationTestsetItem.testset_id == testset_id,
                    EvaluationTestsetItem.tenant_id == tenant_id,
                )
                .order_by(EvaluationTestsetItem.sample_index.asc())
            ).all()
        )
