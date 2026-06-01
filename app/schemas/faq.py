from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class FAQEntryCreate(BaseModel):
    question: str = Field(min_length=1)
    similar_questions: list[str] = Field(default_factory=list)
    answer: str = Field(min_length=1)
    metadata: dict | None = None
    tag_id: str | None = None
    enabled: bool = True


class FAQEntryUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=1)
    similar_questions: list[str] | None = None
    answer: str | None = Field(default=None, min_length=1)
    metadata: dict | None = None
    tag_id: str | None = None
    enabled: bool | None = None


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
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("similar_questions", mode="before")
    @classmethod
    def normalize_similar_questions(cls, value):
        return value or []
