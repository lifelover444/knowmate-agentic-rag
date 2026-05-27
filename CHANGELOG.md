# Changelog

## v0.3

v0.3 对齐 Tencent/WeKnora 的检索增强方向，在 v0.2 Quick Q&A 主链路基础上补齐 keyword/sparse search、RRF hybrid retrieval、可选 rerank、parent-child retrieval expansion 和 Knowledge Search 调试入口。

### Added

- 新增统一检索层 `app/rag/retriever/`：
  - `RetrievalHit`
  - `VectorRetriever`
  - `KeywordRetriever`
  - `HybridRetriever`
  - `RerankPipeline`
  - `ParentChildExpander`
- 新增 keyword/sparse search：
  - 应用层 `jieba` 分词。
  - PostgreSQL FTS 检索。
  - SQLite 测试环境 fallback scoring。
- 新增 hybrid search：
  - vector + keyword 召回。
  - RRF 融合，公式为 `weight / (rrf_k + rank)`。
  - 默认检索模式为 `hybrid`。
- 新增可选 rerank：
  - 继续使用模型类型 `Rerank`。
  - 新增 OpenAI-compatible `/rerank` 风格 `RerankerClient`。
  - 支持 passage cleaning、rerank score 映射和阈值过滤。
- 新增 parent-child retrieval expansion：
  - child chunk 命中后可回填 parent context。
  - sources 保留 matched child 的 chunk id、parent id 和 context id。
- 新增 Knowledge Search API：
  - `POST /api/v1/knowledge-search`
  - 支持 `vector_only / keyword_only / hybrid`。
  - 不调用 LLM，只返回检索 hits 和 score 信息。
- 新增 v0.3 retrieval config 字段：
  - `retrieval_mode`
  - `enable_rerank`
  - `rerank_model_id`
  - `keyword_threshold`
  - `rrf_k`
  - `rrf_vector_weight`
  - `rrf_keyword_weight`
- 新增 `chunks.search_text` 字段和 Alembic migration：
  - `0005_v03_keyword_retrieval`
  - PostgreSQL GIN 表达式索引：`to_tsvector('simple', search_text)`
- 前端工作台新增：
  - 检索模式切换。
  - keyword 阈值、RRF 权重、rerank 开关、Rerank 模型选择。
  - Knowledge Search 调试面板。
  - sources 展示 retrieval method、vector score、keyword score、RRF score、rerank score、context chunk id。
- 新增测试：
  - RRF 排序和去重。
  - rerank passage cleaning、阈值过滤、score 映射。
  - parent-child context expansion。
  - knowledge-search API。
  - v0.3 前端检索控件。

### Changed

- quick-answer 不再直接调用 Qdrant vector search，而是复用统一 Knowledge Search pipeline。
- quick-answer 无可靠来源时继续返回 fallback response，不让 LLM 硬答。
- 文档处理会为每个 chunk 写入 `search_text`，用于 keyword/sparse search。
- `QuickAnswerResponse.sources[]` 保持兼容，同时新增可选检索解释字段：
  - `retrieval_method`
  - `vector_score`
  - `keyword_score`
  - `rrf_score`
  - `rerank_score`
  - `context_chunk_id`

### Not Included

- 不引入 `pg_jieba`。
- 不引入 Elasticsearch/OpenSearch、ParadeDB/pg_search 或真正 BM25 引擎。
- 不实现 GraphRAG、多维索引、Agent、Wiki、URL 导入、多轮会话、流式回答、RBAC。

### Verification

最近一次本地验证：

- `python -m pytest -q`：`44 passed`
- `ruff check .`：通过
- `python -m compileall app tests`：通过
- `npm --prefix frontend run build`：通过
- 本地启动验证：
  - `docker compose up -d postgres redis qdrant`：三项服务 healthy。
  - `alembic upgrade head`：升级到 `0005_v03_keyword_retrieval`。
  - `uvicorn app.main:app`：`/health` 返回 `{"status":"ok"}`。
  - Celery worker：连接 Redis 并 ready。
  - Vite dev server：`http://127.0.0.1:5173` 可访问。

## v0.2.1

v0.2.1 是 v0.3 前的基础 CRUD 补齐版本，主要补齐 WeKnora-style 知识库和文档管理所需的薄 API。

### Added

- 新增知识库列表 API：
  - `GET /api/v1/knowledge-bases`
- 新增知识库更新 API：
  - `PUT /api/v1/knowledge-bases/{kb_id}`
- 新增知识库软删除 API：
  - `DELETE /api/v1/knowledge-bases/{kb_id}`
- 新增知识库下文档列表 API：
  - `GET /api/v1/knowledge-bases/{kb_id}/documents`
- 新增文档软删除 API：
  - `DELETE /api/v1/documents/{document_id}`

### Changed

- 知识库软删除会同步软删除其文档和 chunks。
- 文档软删除会禁用其 chunks，并在 vector store 支持时按 `knowledge_id` 清理向量。
- 列表和计数默认过滤 `deleted_at` 不为空的记录。

## v0.2

v0.2 参考 Tencent/WeKnora 的模型管理、知识库绑定、检索配置和文档重建方向实现，但当前只启用 vector 检索主链路；keyword/BM25、RRF hybrid 和真实 rerank 保留接口边界，后续版本补齐。

### Added

- 新增 WeKnora 风格模型实体：
  - `KnowledgeQA`
  - `Embedding`
  - 预留 `Rerank / VLLM / ASR`
- 新增模型 API：
  - `GET /api/v1/models`
  - `POST /api/v1/models`
  - `GET /api/v1/models/{id}`
  - `PUT /api/v1/models/{id}`
  - `DELETE /api/v1/models/{id}`
  - `POST /api/v1/models/test`
  - `PUT /api/v1/models/{id}/credentials`
  - `DELETE /api/v1/models/{id}/credentials/api_key`
- 新增知识库模型绑定：
  - `embedding_model_id`
  - `summary_model_id`
- 新增租户检索配置：
  - `GET /api/v1/retrieval-config`
  - `PUT /api/v1/retrieval-config`
- 新增文档重处理：
  - `POST /api/v1/documents/{document_id}/reprocess`
  - `POST /api/v1/knowledge-bases/{kb_id}/reprocess`
- 前端工作台新增：
  - QA / Embedding 模型分区管理。
  - DeepSeek / Qwen / OpenAI-compatible 配置入口。
  - 模型测试、Key 尾号展示、知识库绑定、文档重处理按钮。
  - quick-answer sources 展示 score、chunk type、parent id、context header。

### Changed

- 文档处理不再使用全局 active 模型，而是使用知识库绑定的 Embedding 模型。
- quick-answer 不再使用全局 active 模型，而是使用知识库绑定的 Embedding + QA 模型。
- `/api/v1/models/test` 支持两种测试方式：
  - 临时输入 API Key 并立即测试。
  - 已保存模型输入框留空时，使用后端加密保存的 API Key 测试。
- `top_k` 在 quick-answer 请求中继续兼容，但含义调整为最终 sources 上限；未传时使用 `retrieval_config.rerank_top_k`。
- Qdrant collection 按 embedding dimension 使用 `knowmate_embeddings_{dimension}`。
- 重处理前会按 `knowledge_id` 删除旧向量，再替换 PostgreSQL chunks。

### Security

- API Key 继续加密保存。
- 模型读取接口不返回 API Key 明文，只返回：
  - `api_key_configured`
  - `api_key_last4`
- 前端只显示 Key 配置状态和尾号。

### Verification

最近一次本地验证：

- `python -m pytest -q`：`34 passed`
- `ruff check .`：通过
- `python -m compileall app tests`：通过
- `npm --prefix frontend run build`：通过
- 浏览器自测：
  - Qwen QA 连接测试通过。
  - Qwen Embedding `text-embedding-v4` 连接测试通过，检测维度 `1024`。
  - 保存模型后清空输入框，再次点击测试可使用后端加密保存的 Key。
  - 知识库可绑定已保存的 QA 和 Embedding 模型。

### Not Included

- 登录、RBAC、多租户隔离。
- OCR / MinerU / 图片类文件解析。
- 完整 keyword/BM25、RRF hybrid search、真实 rerank。
- query rewrite、多轮会话、流式回答。
- WeKnoraCloud、Ollama 拉取、VLM、ASR。
