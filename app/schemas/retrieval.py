from pydantic import BaseModel, Field, model_validator

RETRIEVAL_MODES = {"vector_only", "keyword_only", "hybrid"}


class RetrievalConfigSchema(BaseModel):
    retrieval_mode: str = Field(default="hybrid")
    embedding_top_k: int = Field(default=50, ge=1, le=500)
    vector_threshold: float = Field(default=0.15, ge=0, le=1)
    keyword_threshold: float = Field(default=0.3, ge=0, le=1)
    rerank_top_k: int = Field(default=10, ge=1, le=50)
    rerank_threshold: float = Field(default=0.2, ge=-10, le=10)
    rerank_model_id: str | None = None
    enable_rerank: bool = False
    rrf_k: int = Field(default=60, ge=1, le=500)
    rrf_vector_weight: float = Field(default=0.7, gt=0, le=10)
    rrf_keyword_weight: float = Field(default=0.3, gt=0, le=10)

    @model_validator(mode="after")
    def validate_retrieval_mode(self):
        if self.retrieval_mode not in RETRIEVAL_MODES:
            raise ValueError("不支持的检索模式")
        return self


def default_retrieval_config() -> dict:
    return RetrievalConfigSchema().model_dump()
