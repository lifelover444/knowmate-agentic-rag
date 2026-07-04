from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvaluationCreate(BaseModel):
    knowledge_base_id: str = Field(min_length=1)
    testset_size: int = Field(default=10, ge=3, le=100)
    top_k: int | None = Field(default=None, ge=1, le=20)
    enable_rerank: bool | None = None
    testset_id: str | None = None


class EvaluationMetricSummary(BaseModel):
    average: float
    min: float | None = None
    max: float | None = None
    count: int = 0


class EvaluationSampleRead(BaseModel):
    id: str
    evaluation_run_id: str
    sample_index: int
    user_input: str
    reference: str | None = None
    reference_contexts: list[str] = Field(default_factory=list)
    expected_chunk_ids: list[str] = Field(default_factory=list)
    expected_law_name: str | None = None
    expected_article_no: str | None = None
    synthesizer_name: str | None = None
    response: str | None = None
    retrieved_contexts: list[str] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    retrieval_trace: dict | None = None
    scores: dict[str, float] = Field(default_factory=dict)
    diagnostics: dict | None = None
    status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class EvaluationRunRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    tenant_id: int
    knowledge_base_id: str
    knowledge_base_name: str | None = None
    testset_id: str | None = None
    testset_source: str = "chunk_derived"
    metric_version: str = "ragas_semantic_v1"
    is_baseline: bool = False
    status: str
    testset_size: int
    top_k: int | None = None
    enable_rerank: bool | None = None
    sample_count: int
    completed_sample_count: int
    failed_sample_count: int
    metrics_summary: dict | None = None
    model_config_payload: dict | None = Field(default=None, alias="model_config")
    evaluator_config: dict | None = None
    baseline_run_id: str | None = None
    baseline_metrics_summary: dict | None = None
    comparison: dict | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class EvaluationRunDetail(EvaluationRunRead):
    samples: list[EvaluationSampleRead] = Field(default_factory=list)


class EvaluationTestsetItemCreate(BaseModel):
    question: str
    reference_answer: str | None = None
    expected_chunk_ids: list[str] = Field(default_factory=list)
    expected_law_name: str | None = None
    expected_article_no: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class EvaluationTestsetCreate(BaseModel):
    knowledge_base_id: str = Field(min_length=1)
    name: str
    description: str | None = None
    items: list[EvaluationTestsetItemCreate] = Field(default_factory=list)


class EvaluationTestsetItemRead(BaseModel):
    id: str
    sample_index: int
    question: str
    reference_answer: str
    expected_chunk_ids: list[str] = Field(default_factory=list)
    expected_law_name: str | None = None
    expected_article_no: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class EvaluationTestsetRead(BaseModel):
    id: str
    tenant_id: int
    knowledge_base_id: str
    knowledge_base_name: str | None = None
    name: str
    description: str | None = None
    item_count: int
    status: str
    created_at: datetime
    updated_at: datetime


class EvaluationTestsetDetail(EvaluationTestsetRead):
    items: list[EvaluationTestsetItemRead] = Field(default_factory=list)
