from datetime import datetime

from pydantic import BaseModel, Field, model_validator

MODEL_TYPES = {"KnowledgeQA", "Embedding", "Rerank", "VLLM", "ASR"}


class ModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: str = Field(min_length=1, max_length=32)
    provider: str = Field(default="openai-compatible", min_length=1, max_length=50)
    source: str = Field(default="remote", min_length=1, max_length=32)
    base_url: str = Field(min_length=1, max_length=512)
    api_key: str | None = Field(default=None, max_length=4096)
    model_name: str = Field(min_length=1, max_length=128)
    embedding_dimension: int | None = Field(default=None, gt=0, le=4096)

    @model_validator(mode="after")
    def validate_model_type(self):
        if self.type not in MODEL_TYPES:
            raise ValueError("不支持的模型类型")
        if self.type == "Embedding" and not self.embedding_dimension:
            raise ValueError("Embedding 模型必须配置向量维度")
        return self


class ModelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    provider: str | None = Field(default=None, min_length=1, max_length=50)
    source: str | None = Field(default=None, min_length=1, max_length=32)
    base_url: str | None = Field(default=None, min_length=1, max_length=512)
    model_name: str | None = Field(default=None, min_length=1, max_length=128)
    embedding_dimension: int | None = Field(default=None, gt=0, le=4096)
    status: str | None = Field(default=None, max_length=32)


class ModelRead(BaseModel):
    id: str
    tenant_id: int
    name: str
    type: str
    provider: str
    source: str
    base_url: str
    model_name: str
    embedding_dimension: int | None
    status: str
    is_builtin: bool
    api_key_configured: bool
    api_key_last4: str | None
    created_at: datetime
    updated_at: datetime


class ModelProviderCredentialField(BaseModel):
    name: str
    label: str
    sensitive: bool = True
    required: bool = True


class ModelProviderPreset(BaseModel):
    value: str
    label: str
    description: str
    model_types: list[str]
    default_urls: dict[str, str]
    default_models: dict[str, str]
    embedding_dimensions: dict[str, int] = Field(default_factory=dict)
    credential_fields: list[ModelProviderCredentialField] = Field(default_factory=list)


class ModelCredentialPayload(BaseModel):
    api_key: str | None = Field(default=None, max_length=4096)


class ModelCredentialsRead(BaseModel):
    fields: dict[str, dict[str, bool]]


class ModelTestPayload(ModelCreate):
    api_key: str | None = Field(default=None, max_length=4096)
    model_id: str | None = Field(default=None, min_length=1, max_length=64)
