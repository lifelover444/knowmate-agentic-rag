from datetime import datetime

from pydantic import BaseModel, Field


class FAQEntryCreate(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    metadata: dict | None = None
    tag_id: str | None = None
    enabled: bool = True


class FAQEntryUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=1)
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
    answer: str
    metadata: dict | None = Field(default=None, validation_alias="faq_metadata")
    tag_id: str | None = None
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
