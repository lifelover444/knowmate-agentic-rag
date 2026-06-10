from pydantic import BaseModel, Field, model_validator

RETRIEVAL_MODES = {"vector_only", "keyword_only", "hybrid"}
V09_FIXED_RETRIEVAL_CONFIG = {
    "retrieval_mode": "hybrid",
    "vector_engine": "qdrant",
    "keyword_engine": "paradedb_bm25",
    "embedding_top_k": 50,
    "keyword_top_k": 50,
    "vector_threshold": 0.15,
    "keyword_threshold": 0.2,
    "rrf_k": 60,
    "rrf_vector_weight": 0.65,
    "rrf_keyword_weight": 0.35,
    "rrf_top_k": 30,
    "rerank_top_k": 8,
    "rerank_threshold": 0.2,
    "enable_rerank": True,
    "enable_parent_child": True,
    "parent_chunk_size": 4096,
    "child_chunk_size": 384,
    "chunk_overlap": 80,
    "final_context_count": 6,
    "max_context_chars": 8000,
}


class RetrievalConfigSchema(BaseModel):
    retrieval_mode: str = Field(default="hybrid")
    vector_engine: str = Field(default="qdrant")
    keyword_engine: str = Field(default="paradedb_bm25")
    embedding_top_k: int = Field(default=50, ge=1, le=500)
    keyword_top_k: int = Field(default=50, ge=1, le=500)
    vector_threshold: float = Field(default=0.15, ge=0, le=1)
    keyword_threshold: float = Field(default=0.2, ge=0, le=1)
    rerank_top_k: int = Field(default=8, ge=1, le=50)
    rerank_threshold: float = Field(default=0.2, ge=-10, le=10)
    rerank_model_id: str | None = None
    enable_rerank: bool = True
    enable_parent_child: bool = True
    rrf_k: int = Field(default=60, ge=1, le=500)
    rrf_vector_weight: float = Field(default=0.65, gt=0, le=10)
    rrf_keyword_weight: float = Field(default=0.35, gt=0, le=10)
    rrf_top_k: int = Field(default=30, ge=1, le=500)
    parent_chunk_size: int = Field(default=4096, ge=512, le=8192)
    child_chunk_size: int = Field(default=384, ge=64, le=2048)
    chunk_overlap: int = Field(default=80, ge=0, le=2000)
    final_context_count: int = Field(default=6, ge=1, le=50)
    max_context_chars: int = Field(default=8000, ge=1000, le=50000)

    @model_validator(mode="after")
    def validate_retrieval_mode(self):
        if self.retrieval_mode not in RETRIEVAL_MODES:
            raise ValueError("不支持的检索模式")
        return self


def default_retrieval_config() -> dict:
    return RetrievalConfigSchema(**V09_FIXED_RETRIEVAL_CONFIG).model_dump()


def normalize_v09_retrieval_config(config: dict | None) -> dict:
    normalized = dict(V09_FIXED_RETRIEVAL_CONFIG)
    if config and config.get("rerank_model_id"):
        normalized["rerank_model_id"] = config["rerank_model_id"]
    return RetrievalConfigSchema(**normalized).model_dump()
