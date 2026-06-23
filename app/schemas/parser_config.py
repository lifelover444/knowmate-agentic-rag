from datetime import datetime

from pydantic import BaseModel, Field


class ParserConfigPayload(BaseModel):
    name: str = Field(default="MinerU", min_length=1, max_length=255)
    base_url: str = Field(default="https://mineru.net/api/v4", min_length=1, max_length=512)
    api_key: str | None = Field(default=None, max_length=4096)
    status: str = Field(default="active", max_length=32)
    config: dict = Field(default_factory=dict)


class ParserConfigRead(BaseModel):
    id: str | None = None
    tenant_id: int
    provider: str
    name: str
    base_url: str
    status: str
    config: dict
    api_key_configured: bool
    api_key_last4: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ParserCredentialPayload(BaseModel):
    api_key: str | None = Field(default=None, max_length=4096)


class ParserCredentialsRead(BaseModel):
    fields: dict[str, dict[str, bool]]
