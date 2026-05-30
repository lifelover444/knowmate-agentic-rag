from datetime import datetime

from pydantic import BaseModel, Field


class VectorStoreBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    provider: str = Field(default="qdrant")
    config_json: dict = Field(default_factory=dict)
    status: str = Field(default="active")
    is_default: bool = False


class VectorStoreCreate(VectorStoreBase):
    pass


class VectorStoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    provider: str | None = None
    config_json: dict | None = None
    status: str | None = None
    is_default: bool | None = None


class VectorStoreTestRequest(BaseModel):
    provider: str = "qdrant"
    config_json: dict = Field(default_factory=dict)


class VectorStoreTestResponse(BaseModel):
    ok: bool
    message: str


class VectorStoreRead(BaseModel):
    id: str
    tenant_id: int
    name: str
    provider: str
    config_json: dict
    status: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
