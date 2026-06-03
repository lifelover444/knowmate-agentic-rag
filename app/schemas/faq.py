from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class FAQEntryCreate(BaseModel):
    question: str = Field(min_length=1)
    similar_questions: list[str] = Field(default_factory=list)
    answer: str = Field(min_length=1)
    metadata: dict | None = None
    tag_id: str | None = None
    enabled: bool = True
    is_recommended: bool = False


class FAQEntryUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=1)
    similar_questions: list[str] | None = None
    answer: str | None = Field(default=None, min_length=1)
    metadata: dict | None = None
    tag_id: str | None = None
    enabled: bool | None = None
    is_recommended: bool | None = None


class FAQEntryRead(BaseModel):
    id: str
    tenant_id: int
    knowledge_base_id: str
    knowledge_id: str
    question: str
    similar_questions: list[str] = Field(default_factory=list)
    answer: str
    metadata: dict | None = Field(default=None, validation_alias="faq_metadata")
    tag_id: str | None = None
    enabled: bool
    is_recommended: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("similar_questions", mode="before")
    @classmethod
    def normalize_similar_questions(cls, value):
        return value or []


class FAQImportFailure(BaseModel):
    row: int
    question: str | None = None
    error: str


class FAQImportProgressRead(BaseModel):
    task_id: str
    knowledge_base_id: str
    status: str
    progress: int
    total: int
    processed: int
    succeeded: int
    failed: int
    imported: int
    failures: list[FAQImportFailure] = Field(default_factory=list)
    errors: list[FAQImportFailure] = Field(default_factory=list)
    error_summary: str | None = None
    mode: str
    import_mode: str
    display_status: str
    processing_time_ms: int
    imported_at: datetime | None = None


class FAQImportDisplayStatusUpdate(BaseModel):
    display_status: str

    @field_validator("display_status")
    @classmethod
    def validate_display_status(cls, value):
        if value not in {"open", "close"}:
            raise ValueError("display_status 必须是 open 或 close")
        return value


class FAQFieldUpdate(BaseModel):
    enabled: bool | None = None
    is_enabled: bool | None = None
    recommended: bool | None = None
    is_recommended: bool | None = None
    tag_id: str | None = None

    def effective_enabled(self) -> bool | None:
        if "enabled" in self.model_fields_set:
            return self.enabled
        if "is_enabled" in self.model_fields_set:
            return self.is_enabled
        return None

    def effective_recommended(self) -> bool | None:
        if "is_recommended" in self.model_fields_set:
            return self.is_recommended
        if "recommended" in self.model_fields_set:
            return self.recommended
        return None

    def has_tag_update(self) -> bool:
        return "tag_id" in self.model_fields_set


class FAQFieldBatchUpdateRequest(BaseModel):
    by_id: dict[str, FAQFieldUpdate] = Field(default_factory=dict)
    by_tag: dict[str, FAQFieldUpdate] = Field(default_factory=dict)
    exclude_ids: list[str] = Field(default_factory=list)

    @field_validator("by_id", "by_tag")
    @classmethod
    def validate_non_empty_keys(cls, value):
        return {str(key): item for key, item in (value or {}).items() if str(key).strip()}


class FAQFieldBatchFailure(BaseModel):
    faq_id: str
    reason: str


class FAQFieldBatchUpdateResponse(BaseModel):
    requested: int
    succeeded: int
    failed: int
    failures: list[FAQFieldBatchFailure] = Field(default_factory=list)
    error_summary: str | None = None
