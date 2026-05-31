# Changelog

## v0.6

v0.6 开发 “会话化 Quick Q&A”，参考 WeKnora 的 session/chat/streaming 方向，但不追 Tencent/WeKnora 官方 v0.6.0 的 RBAC、多工作区、CLI 和 fan-out 全量范围。主线是把 knowmate v0.5 的单轮 Quick Q&A 调试台升级为可持续使用的知识库聊天体验。

### Added

- 新增 `chat_sessions` 和 `chat_messages` 表及 Alembic migration `0009_v06_chat_sessions`。
- 新增 `app/db/repositories/chat.py`、`app/schemas/chat.py` 和 `app/api/v1/chat_sessions.py`。
- 新增会话 API：
  - `GET /api/v1/chat-sessions`
  - `POST /api/v1/chat-sessions`
  - `GET /api/v1/chat-sessions/{session_id}`
  - `PATCH /api/v1/chat-sessions/{session_id}`
  - `DELETE /api/v1/chat-sessions/{session_id}`
  - `GET /api/v1/chat-sessions/{session_id}/messages`
- 新增 `POST /api/v1/quick-answer/stream` SSE 接口，事件包含 session、user_message、rewrite、retrieval、token、final、done。
- assistant 消息保存 sources、retrieval trace 和非敏感 model config 快照。
- 新增可选 query rewrite：有历史消息且开启时复用 KB 绑定 QA 模型改写追问，trace 标注 original query、rewritten query、rewrite_failed 和 rewrite_skipped。
- OpenAI-compatible chat client 新增 streaming completion 边界。
- 前端 `/#/chat` 改为会话化聊天工作台：左侧会话栏、流式消息、会话重命名/删除/pin、query rewrite 开关、每条 assistant 消息 sources/trace 展开面板。
- 保留 knowledge-search 调试入口。

### Changed

- 旧 `POST /api/v1/quick-answer` 保持非流式兼容，但内部复用新的 answer preparation 逻辑。
- Markdown 渲染继续禁用原始 HTML 直通。
- stream quick-answer 继续复用 `KnowledgeSearchService` / retriever pipeline，不新增独立检索链路。

### Not Included

- 不实现完整登录/RBAC/多租户、Agent Mode、Wiki Mode、MCP、IM、小程序、外部数据源同步、OCR/MinerU/VLM/ASR、多 VectorStore fan-out 或真正 BM25。

### Verification

- `python -m pytest -q`：`76 passed`
- `python -m pytest tests/test_v06_chat_sessions.py tests/test_v06_quick_answer_stream.py tests/test_frontend_v06_chat.py -q`：`6 passed`
- `python -m pytest tests/test_quick_answer.py tests/test_v03_knowledge_search.py tests/test_model_config_required.py -q`：`8 passed`
- `ruff check .`：通过
- `python -m compileall app tests`：通过
- `npm --prefix frontend run build`：通过
- Vite dev server `http://127.0.0.1:5174/#/chat` 浏览器烟测：Chat 页面关键控件可见；未启动后端时显示“后端未连接”。

## v0.5

v0.5 开发 “WeKnora-style Knowledge Base Platform Foundation”，在 v0.4 Dashboard 和 v0.3 Quick Q&A 主链路基础上补齐任务中心、FAQ 知识库、per-KB indexing strategy、VectorStore 管理与绑定、文档批量管理，以及 manual text / URL 在线导入边界。

### Added

- 新增 `processing_tasks` 任务中心表和 API：
  - `GET /api/v1/tasks`
  - `GET /api/v1/tasks/{task_id}`
  - `POST /api/v1/tasks/{task_id}/retry`
- 文档上传、单文档重处理、知识库重建均创建任务记录；重处理和重建改为投递 Celery，不在 API 请求内同步处理。
- 新增 `document / faq` 知识库类型。
- 新增 `faq_entries` 表和 FAQ API，FAQ 条目会写入 `knowledges`、`chunks` 和 Qdrant payload，复用 quick-answer / knowledge-search 检索管线。
- 新增 per-KB `indexing_strategy`，支持 `enable_vector`、`enable_keyword`、`enable_parent_child`、`enable_rerank`；`enable_wiki` 和 `enable_knowledge_graph` 仅保存并展示为不可用边界。
- 新增 `vector_stores` 表、Qdrant VectorStore registry/factory 和 VectorStore CRUD / test API，敏感配置读取时脱敏。
- 知识库可绑定 `vector_store_id`。
- 文档列表支持状态、文件类型、关键字筛选，并返回 `chunk_count`、`task_status`、`embedding_model_id`、`processed_at` 和 `error_message`。
- 新增批量删除、批量重处理、manual text / markdown 导入、轻量 URL HTML title + readable text 导入。
- 前端新增：
  - VectorStore 管理页。
  - FAQ 管理页。
  - 知识库创建时选择文档 / FAQ 类型、VectorStore 和 indexing strategy。
  - 文档页筛选、批量操作、任务状态、在线文本导入和 URL 导入。

### Changed

- `KnowledgeSearchService` 会先按 KB `indexing_strategy` 校验请求的 `vector_only / keyword_only / hybrid` 和 rerank 能力，冲突时返回中文可读错误。
- quick-answer 继续复用统一检索管线，并把 KB strategy 冲突作为 400 错误返回。
- Qdrant 默认实例创建集中到 `VectorStoreRegistry`，减少业务服务中散落的 Qdrant 初始化。

### Not Included

- 不实现 Agent Mode、Wiki Mode、MCP 工具、GraphRAG、IM / 小程序或复杂外部数据源同步。
- URL 导入仅做最小 HTML 抽取，不接 Feishu / Notion / Yuque。

### Verification

- `python -m pytest -q`：`66 passed`
- `ruff check .`：通过
- `python -m compileall app tests`：通过
- `npm --prefix frontend run build`：通过

## v0.4

v0.4 不新增后端 API，重点把前端从单页 monolithic 测试工作台重构为 TypeScript 化、组件化的 WeKnora-style 浅色 Dashboard。后端 Quick Q&A、knowledge-search、模型管理、检索配置、文档处理等能力保持原有端点和响应形态。

### Added

- 新增 TypeScript 前端配置：
  - `frontend/tsconfig.json`
  - `frontend/tsconfig.node.json`
  - `frontend/src/env.d.ts`
- 新增 Vue Router hash 路由：
  - `/#/chat`
  - `/#/knowledge-bases`
  - `/#/knowledge-bases/:kbId/documents`
  - `/#/settings/models`
  - `/#/settings/retrieval`
- 新增 Pinia store 分层：
  - `models`
  - `knowledgeBase`
  - `retrieval`
  - `chat`
- 新增复用组件：
  - `AppSidebar`
  - `ModelConfigForm`
  - `DocumentUpload`
  - `ChunkPreview`
  - `SourceCard`
- 新增业务视图：
  - `ChatView`
  - `KnowledgeBaseView`
  - `DocumentsView`
  - `ModelSettingsView`
  - `RetrievalSettingsView`
- 新增前端 API 类型定义和请求封装：
  - `frontend/src/types/api.ts`
  - `frontend/src/utils/api.ts`
- 新增 Markdown 回答渲染：
  - 使用 `markdown-it`
  - `html: false`，不让回答中的 HTML 直通 `v-html`
  - 使用 `highlight.js` 支持代码块高亮

### Changed

- 前端运行时依赖改为 Vue 3 + TypeScript + Vite + Arco Design Vue + Pinia + vue-router。
- 移除 `lucide-vue-next`，不再保留旧绿色单页测试台样式。
- `App.vue` 只负责全局布局，业务 API 调用迁移到 stores 和视图组件。
- `main.js` 迁移为 `main.ts`。
- `apiErrors.js` 迁移为 `utils/api.ts`，继续保留非 JSON 错误响应处理和中文可读错误格式化。
- `styles.css` 迁移为 `styles/app.css`，采用浅色 WeKnora 风格：
  - 近白页面背景
  - 白色内容卡片
  - 绿色品牌主色
  - 低饱和边框和浅绿色选中态
- `vite.config.js` 保留 `/api` proxy，并新增 `/health` proxy。
- `package.json` 新增 `type-check`，`build` 会先执行 `vue-tsc --noEmit` 再执行 `vite build`。
- 前端字符串测试改为扫描 `frontend/src/**/*.{vue,ts,css}`，适配组件化结构。

### Preserved

- 不新增后端 API。
- 不修改 `app/` 后端代码。
- 继续调用现有 v0.3 端点：
  - 模型 CRUD、模型测试、凭据更新
  - 检索配置加载和保存
  - parser engine 加载
  - chunker preview
  - 知识库创建、列表、详情、删除、重建
  - 文档列表、上传、状态轮询、chunks 查看、重处理、删除
  - quick-answer
  - knowledge-search
- API Key 仍不回显明文，只展示配置状态和尾号。
- 文档解析轮询仍为最多 300 次、每秒一次。
- sources 继续展示 `retrieval_method`、`vector_score`、`keyword_score`、`rrf_score`、`rerank_score`、`context_chunk_id`、`parent_chunk_id`、`chunk_type` 等检索解释字段。

### Verification

最近一次本地验证：

- `npm --prefix frontend run build`：通过
- `python -m pytest -q`：`51 passed`

## v0.3.1

v0.3.1 是 v0.3 的质量补齐版本，不新增功能，修复审查中发现的疏漏。

### Fixed

- 清理遗留 `QuickAnswerEngine` 类，消除 v0.2 双路径，`AnswerSource` / `AnswerResult` 保留在原模块以维持现有 import 兼容。
- 修复 `FakeVectorStore.search()` 缺少 `score_threshold` 参数导致测试走 TypeError 降级路径。
- 统一 keyword/vector hit 的 title 来源。
- `SourceRead` 新增可选 `context_content` 字段，便于前端调试展示 parent context。

### Added

- 补充 `tokenize_query` 单元测试（纯中文/纯英文/中英混合/短 term 过滤/空 query）。
- 补充软删除文档后的检索排除集成测试（keyword_only + hybrid）。

### Verification

最近一次本地验证：

- `python -m pytest -q`：`51 passed`
- `ruff check .`：通过
- `python -m compileall app tests`：通过

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
