# knowmate 知友

knowmate 知友是一个参考 [Tencent/WeKnora](https://github.com/Tencent/WeKnora) 核心思路实现的知识库 RAG 项目。后端技术栈从 WeKnora 的 Go 实现改为 Python / FastAPI；项目不是 Tencent/WeKnora 官方项目。

当前版本为 v0.71，主线仍聚焦 WeKnora-style Quick Q&A。v0.71 在 v0.7 知识库平台化基础上，继续补齐 Quick Q&A 操作闭环与可观测性：上传队列、文档下载 / 取消解析 / 移动、停止生成、自动标题、last-request state、阶段化 retrieval trace、真实运行状态 API 和 Command Palette：

```text
模型管理
  -> 知识库绑定 QA / Embedding 模型
  -> 标签组织
  -> 文档上传
  -> 上传队列 / 多文件进度
  -> Celery Worker 解析文档
  -> Adaptive Chunking 切片
  -> 文档预览 / chunk outline
  -> 生成 embedding
  -> chunk 元数据写 PostgreSQL
  -> 向量写 Qdrant
  -> FAQ 导入导出 / FAQ 检索测试
  -> FAQ 相似问法 / FAQ 索引模式
  -> quick-answer / knowledge-search
  -> 多知识库 / 文件范围检索
  -> vector + keyword 召回
  -> RRF hybrid merge
  -> optional rerank
  -> parent-child context expansion
  -> optional query rewrite
  -> chat model 生成 answer
  -> 返回 answer + sources + retrieval trace
  -> 阶段化 retrieval trace
  -> sources 显示知识库来源
  -> 保存 chat session / messages
  -> Chat mention scope
  -> 停止生成 / 自动标题 / last-request state
  -> 会话搜索 / 批量删除 / 推荐问题
  -> 文档处理 timeline
  -> 文档下载 / 取消解析 / 移动 KB
  -> runtime status / Command Palette
```

## 当前进度

已完成：

- FastAPI 后端骨架：API router、service、repository、配置、日志、健康检查。
- PostgreSQL 元数据存储：知识库、文档、chunks、租户检索配置、模型实体等表结构和 Alembic migration。
- WeKnora 风格模型管理：
  - `KnowledgeQA` 和 `Embedding` 两类模型可创建、编辑、删除、测试。
  - 预留 `Rerank / VLLM / ASR` 类型枚举。
  - 支持 Qwen / DashScope、DeepSeek、OpenAI-compatible 配置。
  - API Key 加密保存，读取接口只返回配置状态和尾号，不返回明文。
  - 旧 `/api/v1/model-config` 兼容接口仍保留。
- 知识库模型绑定：
  - 创建知识库必须选择可用的 `Embedding` 和 `KnowledgeQA` 模型。
  - 文档处理使用知识库绑定的 Embedding 模型。
  - quick-answer 使用知识库绑定的 Embedding + QA 模型。
  - 模型缺失、停用、类型不匹配时返回中文可读错误。
- WeKnora 风格检索配置：
  - 单租户 `retrieval_config` JSON。
  - 默认模式：`retrieval_mode=hybrid`。
  - 默认值：`embedding_top_k=50`、`vector_threshold=0.15`、`keyword_threshold=0.3`、`rerank_top_k=10`、`rerank_threshold=0.2`、`rrf_k=60`、`rrf_vector_weight=0.7`、`rrf_keyword_weight=0.3`、`enable_rerank=false`。
  - 支持 `vector_only / keyword_only / hybrid` 三种检索模式。
- v0.3 检索增强：
  - 新增统一 `app/rag/retriever/` 检索层。
  - `VectorRetriever` 包装 Qdrant dense retrieval。
  - `KeywordRetriever` 使用应用层 `jieba` 分词 + PostgreSQL FTS fallback，v0.3 先称 keyword/sparse search，不强称完整 BM25。
  - `HybridRetriever` 使用 RRF 公式 `weight / (rrf_k + rank)` 融合 vector 和 keyword 结果。
  - `RerankPipeline` 支持 passage cleaning、阈值过滤和 score 映射。
  - `ParentChildExpander` 支持 child 命中后回填 parent context，sources 仍保留 matched child 信息。
  - 新增 `POST /api/v1/knowledge-search`，用于不调用 LLM 的检索调试。
- v0.3.1 质量补齐：
  - 清理 v0.2 遗留 `QuickAnswerEngine`，quick-answer 只保留统一 `KnowledgeSearchService` / retriever pipeline 路径。
  - `AnswerSource` / `AnswerResult` 保留在 `app/rag/quick_answer.py`，维持现有 import 兼容。
  - 修复测试夹具 `FakeVectorStore.search()` 的 `score_threshold` 参数和阈值过滤，避免测试误走 TypeError 降级路径。
  - keyword hit 的 title 在 chunk metadata 缺失时回退到文档标题，和 vector payload title 保持一致。
  - `SourceRead` 新增可选 `context_content`，用于透传 parent chunk context。
  - 补充 `tokenize_query`、软删除后检索排除、QuickAnswerService fallback 和 parent context 序列化测试。
- Redis + Celery 后台文档处理：上传后异步解析、切分、embedding、写入 Qdrant。
- Qdrant 向量存储：按 embedding dimension 使用 collection `knowmate_embeddings_{dimension}`。
- PostgreSQL keyword 检索字段：
  - `chunks.search_text` 存储标题、context header 和 chunk content 的检索文本。
  - Alembic `0005_v03_keyword_retrieval` 为 PostgreSQL 添加 `to_tsvector('simple', search_text)` GIN 表达式索引。
- v0.2.1 基础 CRUD 补齐：
  - 知识库列表、更新、软删除。
  - 文档软删除。
  - 知识库下文档列表。
- 文档重处理：
  - 单文档重处理。
  - 知识库批量重处理。
  - 重处理前按 `knowledge_id` 清理旧向量并替换 PostgreSQL chunks。
- WeKnora 风格通用解析注册表：`builtin` 支持 `.txt/.md/.pdf/.docx/.csv/.json/.xlsx`。
- WeKnora 风格自适应切分：`auto / heading / heuristic / legacy`，支持 protected blocks、context header、parent-child chunking。
- Chunking preview/debug API：可预览命中策略、profile、chunk 统计和切片内容。
- v0.4 Vue / TypeScript Dashboard：
  - 使用 Vue 3、Vite、TypeScript、Arco Design Vue、Pinia、vue-router、markdown-it 和 highlight.js。
  - 使用 hash router，生产路径形态为 `/#/chat`、`/#/knowledge-bases`、`/#/knowledge-bases/:kbId/documents`、`/#/knowledge-bases/:kbId/faqs`、`/#/settings`。
  - 从旧单文件 `App.vue` 拆分为布局、复用组件、Pinia stores、API utils、类型定义和多个业务视图。
  - 页面覆盖快速问答、知识搜索、知识库列表、文档管理、FAQ 管理、设置中心、模型配置、VectorStore、检索配置和切分预览。
  - 保持 WeKnora 风格浅色界面：近白页面背景、绿色品牌主色、低饱和边框、中文企业软件观感。
  - quick-answer 回答使用 `markdown-it` 渲染，禁用 HTML 直通，sources 使用复用 `SourceCard` 展示完整检索 metadata。
- v0.5 Knowledge Base Platform Foundation：
  - 新增 `processing_tasks` 任务中心，统一记录上传处理、单文档重处理、知识库重建任务。
  - 单文档重处理和知识库重建改为创建任务并投递 Celery，不再在 API 请求内同步处理。
  - 新增 `document / faq` 两类知识库，FAQ 条目写入 `faq_entries`、`knowledges`、`chunks` 和 Qdrant payload，复用 quick-answer / knowledge-search 检索管线。
  - 新增 per-KB `indexing_strategy`，支持 vector、keyword、parent-child、rerank 能力开关，Wiki / Knowledge Graph 仅保存并展示为不可用边界。
  - 新增 `vector_stores` 表、Qdrant VectorStore registry/factory 和 VectorStore CRUD / test API；敏感配置读取时脱敏。
  - 文档列表支持状态、文件类型、关键字筛选，并返回 `chunk_count`、`task_status`、`embedding_model_id`、`processed_at` 和失败原因。
  - 新增批量删除、批量重处理、manual text / markdown 导入、轻量 URL HTML title + readable text 导入。
  - 前端新增 VectorStore 管理页、FAQ 管理页、知识库类型/索引策略/VectorStore 选择、任务状态和批量操作入口。
- v0.6 会话化 Quick Q&A：
  - 新增 `chat_sessions` / `chat_messages` 表、repository、schemas 和 Alembic migration。
  - 新增会话 API，支持列表、详情、创建、重命名、删除、pin/unpin 和消息列表。
  - 新增 `POST /api/v1/quick-answer/stream` SSE 接口，保留旧 `/api/v1/quick-answer` 非流式行为。
  - 流式回答继续复用 `KnowledgeSearchService` / retriever pipeline，不另写检索链路。
  - assistant message 保存 `sources_json`、`retrieval_trace_json` 和非敏感 `model_config_json`。
  - query rewrite 作为可选能力：有历史消息且开启时复用 KB 绑定 QA 模型改写追问，trace 展示 original / rewritten query 和失败/跳过状态。
  - 前端 `/#/chat` 升级为会话化聊天工作台：左侧会话栏、流式消息、每条 assistant 消息 sources/trace 折叠面板、基础会话设置和保留的检索调试入口。
- v0.61 WeKnora 对齐补强：
  - 新增知识库标签体系：标签 CRUD、文档/FAQ 标签筛选、批量设置标签，并把 `tag_id` 写入 Knowledge、FAQEntry、Chunk 和 Qdrant payload。
  - 新增文档预览 API 和前端预览抽屉，展示摘要、正文预览、chunk outline 和 chunk 内容导航。
  - 新增 FAQ CSV/XLSX 导入导出，支持 append/replace、逐行失败摘要、metadata、enabled 和 tag_id。
  - FAQ 管理页新增导入结果卡片、导出按钮和 FAQ 检索测试抽屉。
  - 批量删除/重处理响应新增 requested/succeeded/failed/failures，任务列表新增 batch_summary，文档页展示批处理进度和失败任务重试。
  - 新增 `/#/settings` 设置中心外壳，整合模型、VectorStore、检索、解析器和存储状态；parser/storage provider 未接入项以禁用占位展示。
  - 会话列表支持搜索、批量删除；新会话空态展示来自 FAQ 和 chunk generated_questions 的推荐问题。
- v0.7 WeKnora P0 对齐：
  - 知识库列表和详情返回 WeKnora-like `capabilities`，支持单租户 KB pin/unpin 和置顶排序。
  - 新增 KB 详情一体化页面骨架，把概览、文档/FAQ 工作流、设置、任务/状态入口收敛到同一页面。
  - KB 设置面板支持创建后编辑基础信息、模型绑定、parser rules、chunking config、indexing strategy 和 vector store，保存后提示需要重处理/重建索引。
  - `knowledge-search` 和 `quick-answer` 支持 `knowledge_base_ids` 与 `knowledge_ids` scope，允许多知识库或文件范围检索，并校验跨 KB embedding 模型一致性。
  - Chat 工作台新增显式 KB/file scope 选择和 mention chips；用户消息保存并展示 `mentioned_items`，sources 展示 `knowledge_base_name`。
  - 新增文档处理 spans/timeline：parse、chunk、embed、upsert、finalize 五阶段记录状态、耗时、错误和 downstream cancelled，历史文档返回安全占位。
  - 文档列表、预览抽屉和处理时间线抽屉展示五阶段处理状态。
  - FAQ 支持 `similar_questions`，导入导出新增 `similar_questions` 列。
  - FAQ KB 支持 `faq_config.index_mode` 与 `faq_config.question_index_mode`，按 question_only/question_answer 和 combined/separate 生成检索 chunk 与向量 payload。
  - FAQ 管理页展示相似问法，编辑弹窗可输入相似问法，检索测试展示 `matched_question`。
- v0.71 Quick Q&A 操作闭环与可观测性：
  - 文档上传组件支持多文件上传队列，逐文件展示 pending / uploading / queued / processing / completed / failed 状态，并区分上传失败、解析失败和部分成功。
  - 文档管理新增原文件下载、queued/processing 取消解析和移动到其他兼容知识库；取消解析会同步任务状态和处理 timeline。
  - 同一知识库内活跃重复文件上传返回中文 409 错误；已软删除的同一文件允许重新上传，避免复用旧 deterministic document id 触发主键冲突。
  - Quick Answer stream 支持停止生成；停止后保存 partial assistant message 为 cancelled。
  - 空白或占位会话标题会在首问后自动生成；会话保存 `last_request_state`，前端展示最近一次请求状态、scope、命中数、模型摘要和耗时。
  - retrieval trace 新增 rewrite / search / rerank / answer 阶段列表，包含状态、耗时和输出摘要。
  - 新增 `/api/v1/runtime-status`，返回 database、local storage、vector store、parser registry 等运行状态，设置页使用真实状态而不是静态占位。
  - 新增全局 Command Palette，支持按钮和 Ctrl/Meta+K 打开，快速跳转 Chat、知识库、文档、FAQ、模型、检索、解析器和存储状态。
- 自动化测试：覆盖多模型 CRUD、凭据加密、知识库模型校验、重处理、检索配置、hybrid/RRF/rerank/parent-child retrieval、knowledge-search API、前端关键逻辑、API 和文档处理 payload。
- v0.71 质量验证详见下方“验证命令”和 [CHANGELOG.md](CHANGELOG.md)。

暂未实现：

- 登录、RBAC、多租户隔离。
- OCR / MinerU / 图片类文件解析。
- 真正 BM25 引擎、pg_jieba、Elasticsearch/OpenSearch、ParadeDB/pg_search。
- GraphRAG、多维索引、Agent Mode、Wiki Mode。
- WeKnoraCloud、Ollama 拉取、VLM、ASR。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 后端 | Python 3.11+, FastAPI, Pydantic, SQLAlchemy |
| 数据库 | PostgreSQL, Alembic |
| 异步任务 | Celery, Redis |
| 向量库 | Qdrant |
| 模型接入 | OpenAI Python SDK, OpenAI-compatible API, OpenAI-compatible rerank API |
| 检索 | Qdrant dense retrieval, PostgreSQL FTS, jieba, RRF |
| 前端 | Vue 3, TypeScript, Vite, Arco Design Vue, Pinia, vue-router, markdown-it, highlight.js |
| 测试与质量 | pytest, Ruff |

## 快速启动

### 1. 安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

npm --prefix frontend install
npm --prefix frontend run build
```

如果只做前端开发并且 `frontend/node_modules` 已存在，可以跳过 `npm install`。

### 2. 配置环境变量

```powershell
Copy-Item .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

把生成的 Fernet key 写入 `.env`：

```env
MODEL_CONFIG_ENCRYPTION_KEY=your-generated-fernet-key
```

`.env` 不要提交到 Git。模型 API Key 推荐在页面里配置，后端会加密保存到数据库。

### 3. 启动基础设施

Docker Compose 只包含基础依赖服务：

```powershell
docker compose up -d postgres redis qdrant
```

确认容器 healthy 后执行数据库迁移：

```powershell
alembic upgrade head
```

`alembic upgrade head` 会把 PostgreSQL 表结构升级到当前代码需要的最新版本，例如 v0.3 的模型实体、知识库模型绑定、检索配置字段和 `chunks.search_text`。不执行迁移时，后端可能会因为缺表或缺字段报错。

### 4. 启动 API

```powershell
uvicorn app.main:app --reload
```

后端地址：

- 工作台：http://127.0.0.1:8000
- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

### 5. 启动 Worker

Windows / PowerShell：

```powershell
celery -A app.workers.celery_app:celery_app worker --loglevel=info --pool=solo
```

macOS / Linux：

```bash
celery -A app.workers.celery_app:celery_app worker --loglevel=info
```

Celery worker 负责后台文档处理。文档上传后，解析、切分、embedding、写入 Qdrant 都由 worker 执行。不启动 worker，文档可能会停留在 `pending` 或 `processing`。

### 6. 前端开发模式

后端在 `http://127.0.0.1:8000` 运行时，可以另开一个 PowerShell：

```powershell
npm --prefix frontend run dev
```

访问：

```text
http://127.0.0.1:5173
```

Vite 会把 `/api` 和 `/health` 代理到 `http://127.0.0.1:8000`。

## 页面使用流程

1. 进入 `/#/settings`，在“模型配置”分区分别配置 QA、Embedding 和可选 Rerank 模型。
2. QA 模型可选择 Qwen / DashScope、DeepSeek 或 OpenAI-compatible；Embedding 模型当前主要使用 Qwen / DashScope。
3. 填入 API Key 后点击“测试模型”。
4. 保存模型后，API Key 输入框会清空；再次测试会使用后端已加密保存的 Key。
5. 在 `/#/settings` 的“检索与分块”分区配置 `hybrid / vector_only / keyword_only`、keyword 阈值、RRF 权重、rerank 开关、parser engine 和 chunking strategy，可先点“切分预览”。
6. 进入 `/#/knowledge-bases` 创建知识库，知识库会绑定选择的 QA 和 Embedding 模型，并保存切分配置与解析规则。
7. 进入知识库的文档管理页，上传 `.txt/.md/.pdf/.docx/.csv/.json/.xlsx` 文档，可按标签组织文档。
8. 等待 Worker 处理到“解析完成”，页面可在预览抽屉中查看摘要、outline 和 chunks。
9. FAQ 知识库可进入 `/#/knowledge-bases/:kbId/faqs`，手动维护 FAQ，或使用 CSV/XLSX append/replace 导入并导出。
10. 切换向量模型、维度或切分参数后，点击“重新处理”或“重建知识库”重建向量；批量操作结果会显示成功/失败摘要。
11. 进入 `/#/chat`，选择知识库后新建会话，或从左侧会话列表继续历史会话；可搜索会话、批量删除会话，空会话会显示推荐问题。
12. 在输入区提问，页面会流式追加 assistant 消息；每条回答可展开来源依据和 retrieval trace。
13. 需要调试召回时，展开“检索调试”，只返回 sources，不调用 LLM。

## 核心 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 健康检查 |
| `GET` | `/api/v1/model-config` | 兼容接口：查询旧 active 模型配置 |
| `PUT` | `/api/v1/model-config` | 兼容接口：保存旧 active 模型配置 |
| `POST` | `/api/v1/model-config/test` | 兼容接口：测试旧模型配置 |
| `GET` | `/api/v1/models?type=Embedding` | 查询模型列表，可按类型过滤 |
| `POST` | `/api/v1/models` | 创建模型 |
| `GET` | `/api/v1/models/{id}` | 查询模型 |
| `PUT` | `/api/v1/models/{id}` | 更新模型基础信息 |
| `DELETE` | `/api/v1/models/{id}` | 删除模型 |
| `POST` | `/api/v1/models/test` | 测试 QA 或 Embedding 模型 |
| `PUT` | `/api/v1/models/{id}/credentials` | 更新模型凭据 |
| `DELETE` | `/api/v1/models/{id}/credentials/api_key` | 清除模型 API Key |
| `GET` | `/api/v1/retrieval-config` | 查询租户检索配置 |
| `PUT` | `/api/v1/retrieval-config` | 更新租户检索配置 |
| `GET` | `/api/v1/parser-engines` | 查询 parser engine 可用性 |
| `POST` | `/api/v1/chunker/preview` | 预览切分结果 |
| `POST` | `/api/v1/knowledge-bases` | 创建知识库，必须绑定 QA 和 Embedding 模型 |
| `GET` | `/api/v1/knowledge-bases` | 查询知识库列表 |
| `GET` | `/api/v1/knowledge-bases/{kb_id}` | 查询知识库 |
| `PUT` | `/api/v1/knowledge-bases/{kb_id}` | 更新知识库基础信息和配置 |
| `DELETE` | `/api/v1/knowledge-bases/{kb_id}` | 软删除知识库 |
| `GET` | `/api/v1/knowledge-bases/{kb_id}/tags` | 查询知识库标签，可按关键字过滤 |
| `POST` | `/api/v1/knowledge-bases/{kb_id}/tags` | 创建标签 |
| `PUT` | `/api/v1/knowledge-bases/{kb_id}/tags/{tag_id}` | 更新标签 |
| `DELETE` | `/api/v1/knowledge-bases/{kb_id}/tags/{tag_id}` | 删除标签 |
| `PUT` | `/api/v1/knowledge-bases/{kb_id}/documents/tags` | 批量设置文档标签 |
| `PUT` | `/api/v1/knowledge-bases/{kb_id}/faqs/tags` | 批量设置 FAQ 标签 |
| `GET` | `/api/v1/knowledge-bases/{kb_id}/documents` | 查询知识库下文档列表 |
| `POST` | `/api/v1/knowledge-bases/{kb_id}/documents/text` | manual text / markdown 在线导入 |
| `POST` | `/api/v1/knowledge-bases/{kb_id}/documents/url` | URL 在线导入 |
| `POST` | `/api/v1/knowledge-bases/{kb_id}/documents/batch-delete` | 批量删除文档 |
| `POST` | `/api/v1/knowledge-bases/{kb_id}/documents/batch-reprocess` | 批量重处理文档 |
| `POST` | `/api/v1/knowledge-bases/{kb_id}/reprocess` | 批量重处理知识库文档 |
| `POST` | `/api/v1/knowledge-bases/{kb_id}/documents/file` | 上传文档 |
| `GET` | `/api/v1/knowledge-bases/{kb_id}/faqs` | 查询 FAQ 条目 |
| `POST` | `/api/v1/knowledge-bases/{kb_id}/faqs` | 新增 FAQ 条目并写入索引 |
| `PUT` | `/api/v1/knowledge-bases/{kb_id}/faqs/{faq_id}` | 更新、启用或停用 FAQ 条目 |
| `DELETE` | `/api/v1/knowledge-bases/{kb_id}/faqs/{faq_id}` | 删除 FAQ 条目 |
| `POST` | `/api/v1/knowledge-bases/{kb_id}/faqs/{faq_id}/rebuild-index` | 重建 FAQ 索引 |
| `POST` | `/api/v1/knowledge-bases/{kb_id}/faqs/import` | CSV/XLSX 导入 FAQ，支持 append/replace |
| `GET` | `/api/v1/knowledge-bases/{kb_id}/faqs/export?format=csv` | 导出 FAQ CSV |
| `GET` | `/api/v1/knowledge-bases/{kb_id}/faqs/export?format=xlsx` | 导出 FAQ XLSX |
| `GET` | `/api/v1/documents/{document_id}` | 查询文档处理状态 |
| `DELETE` | `/api/v1/documents/{document_id}` | 软删除文档 |
| `GET` | `/api/v1/documents/{document_id}/chunks` | 查询文档切片 |
| `GET` | `/api/v1/documents/{document_id}/preview` | 查询文档摘要、正文预览和 chunk outline |
| `POST` | `/api/v1/documents/{document_id}/reprocess` | 重处理单个文档 |
| `GET` | `/api/v1/documents/{document_id}/download` | 下载文档原文件 |
| `POST` | `/api/v1/documents/{document_id}/cancel-parse` | 取消 queued/processing 文档解析 |
| `POST` | `/api/v1/documents/move` | 移动文档到其他兼容知识库 |
| `POST` | `/api/v1/knowledge-search` | 知识搜索，只返回检索 hits，不调用 LLM |
| `POST` | `/api/v1/quick-answer` | 快速问答 |
| `POST` | `/api/v1/quick-answer/stream` | 流式快速问答，返回 SSE events 并保存会话消息 |
| `GET` | `/api/v1/chat-sessions?keyword=` | 查询会话列表，可按标题和消息内容搜索 |
| `POST` | `/api/v1/chat-sessions` | 创建会话 |
| `POST` | `/api/v1/chat-sessions/batch-delete` | 批量软删除会话 |
| `GET` | `/api/v1/chat-sessions/recommended-questions` | 查询当前知识库推荐问题 |
| `GET` | `/api/v1/chat-sessions/{session_id}` | 查询会话详情和消息 |
| `PATCH` | `/api/v1/chat-sessions/{session_id}` | 更新会话标题、置顶状态和设置 |
| `DELETE` | `/api/v1/chat-sessions/{session_id}` | 软删除会话 |
| `GET` | `/api/v1/chat-sessions/{session_id}/messages` | 查询会话消息 |
| `POST` | `/api/v1/chat-sessions/{session_id}/stop` | 停止当前会话流式生成 |
| `GET` | `/api/v1/runtime-status` | 查询数据库、存储、向量库和 parser registry 运行状态 |
| `GET` | `/api/v1/tasks` | 查询任务中心 |
| `GET` | `/api/v1/tasks/{task_id}` | 查询单个任务 |
| `POST` | `/api/v1/tasks/{task_id}/retry` | 重试失败任务 |
| `GET` | `/api/v1/vector-stores` | 查询 VectorStore |
| `POST` | `/api/v1/vector-stores` | 创建 VectorStore |
| `GET` | `/api/v1/vector-stores/{id}` | 查询 VectorStore |
| `PUT` | `/api/v1/vector-stores/{id}` | 更新 VectorStore |
| `DELETE` | `/api/v1/vector-stores/{id}` | 删除 VectorStore |
| `POST` | `/api/v1/vector-stores/test` | 测试 VectorStore 配置 |

## v0.5 Schema 变化

`KnowledgeBaseCreate` / `KnowledgeBaseRead` 新增：

```json
{
  "kb_type": "document",
  "vector_store_id": null,
  "indexing_strategy": {
    "enable_vector": true,
    "enable_keyword": true,
    "enable_parent_child": false,
    "enable_rerank": false,
    "enable_wiki": false,
    "enable_knowledge_graph": false
  }
}
```

`DocumentRead` 新增：

```json
{
  "source_type": "file",
  "embedding_model_id": "embedding model id",
  "chunk_count": 0,
  "task_status": "queued"
}
```

## v0.7 Schema / API 变化

`KnowledgeBaseRead` 新增或强化：

```json
{
  "capabilities": {
    "document": true,
    "faq": false,
    "vector": true,
    "keyword": true,
    "parent_child": false,
    "rerank": false,
    "wiki": false,
    "graph": false
  },
  "is_pinned": true,
  "pinned_at": "2026-05-31T12:00:00Z",
  "faq_config": {
    "index_mode": "question_answer",
    "question_index_mode": "combined"
  }
}
```

新增 KB pin API：

```http
PUT /api/v1/knowledge-bases/{kb_id}/pin
```

请求体：

```json
{
  "pinned": true
}
```

`knowledge-search` / `quick-answer` scope 支持：

```json
{
  "knowledge_base_ids": ["kb-a", "kb-b"],
  "knowledge_ids": ["document-or-faq-knowledge-id"]
}
```

`SourceRead` 新增可选 `knowledge_base_name`，用于多 KB 检索后的来源展示。

`FAQEntryRead` / 创建 / 更新 / 导入导出新增 `similar_questions`：

```json
{
  "question": "发票怎么申请？",
  "similar_questions": ["哪里下载发票", "发票入口在哪"],
  "answer": "..."
}
```

新增文档处理 timeline API：

```http
GET /api/v1/documents/{document_id}/spans
```

返回 root span、当前 attempt 和 parse/chunk/embed/upsert/finalize 五阶段状态；历史文档无 span 时返回 attempt `0` 占位阶段。

## v0.71 Schema / API 变化

文档上传行为：

- 同一知识库内存在活跃同 hash 文件时，上传接口返回 `409 Conflict` 和中文错误 `该文件已上传，请勿重复上传。`。
- 如果历史同 hash 文件已经软删除，重新上传会生成新的 document id，不复用已删除记录的主键。

文档生命周期新增：

```http
GET /api/v1/documents/{document_id}/download
POST /api/v1/documents/{document_id}/cancel-parse
POST /api/v1/documents/move
```

`DocumentMoveRequest`：

```json
{
  "document_ids": ["document-id"],
  "target_knowledge_base_id": "target-kb-id"
}
```

会话生成生命周期新增：

```http
POST /api/v1/chat-sessions/{session_id}/stop
```

`ChatSessionRead.settings.last_request_state` 会保存最近一次请求的非敏感状态，例如：

```json
{
  "status": "completed",
  "knowledge_base_ids": ["kb-id"],
  "knowledge_ids": [],
  "hit_count": 5,
  "model": "qwen-max",
  "elapsed_ms": 1234
}
```

`retrieval_trace` 新增阶段列表：

```json
{
  "stages": [
    {
      "name": "search",
      "status": "completed",
      "duration_ms": 35,
      "summary": "hybrid hits: 5"
    }
  ]
}
```

运行状态新增：

```http
GET /api/v1/runtime-status
```

返回 database、local storage、vector store、parser registry 和 system 概览，供设置页展示真实状态。

## v0.61 Schema 变化

新增 `KnowledgeTagRead`：

```json
{
  "id": "tag id",
  "knowledge_base_id": "KB ID",
  "name": "产品文档",
  "color": "#16c784",
  "sort_order": 0,
  "knowledge_count": 3,
  "chunk_count": 18
}
```

`DocumentRead` / `FAQEntryRead` / `ChunkRead` 新增可选 `tag_id`，Qdrant payload 同步写入 `tag_id` 以便来源展示和筛选。

批量文档操作响应新增部分失败摘要：

```json
{
  "requested": 3,
  "succeeded": 2,
  "failed": 1,
  "deleted": 2,
  "queued": 0,
  "task_ids": [],
  "failures": [
    {
      "document_id": "missing-doc",
      "reason": "document not found"
    }
  ]
}
```

任务响应新增 `batch_summary`：

```json
{
  "batch_summary": {
    "total": 3,
    "queued": 1,
    "processing": 0,
    "completed": 1,
    "failed": 1,
    "failures": [
      {
        "task_id": "task id",
        "document_id": "document id",
        "error_message": "解析失败"
      }
    ]
  }
}
```

文档预览响应：

```json
{
  "id": "document id",
  "title": "文档标题",
  "status": "completed",
  "summary": "文档摘要",
  "content_preview": "正文预览",
  "chunks": [
    {
      "id": "chunk id",
      "chunk_index": 0,
      "chunk_type": "text",
      "context_header": "章节标题",
      "content_preview": "chunk 内容预览"
    }
  ]
}
```

会话批量删除响应：

```json
{
  "requested": 3,
  "deleted": 2,
  "failed": 1,
  "failures": [
    {
      "session_id": "missing-session",
      "reason": "chat session not found"
    }
  ]
}
```

推荐问题响应：

```json
{
  "items": [
    {
      "question": "如何申请退款？",
      "source_type": "faq",
      "knowledge_base_id": "KB ID",
      "faq_id": "FAQ ID"
    },
    {
      "question": "上传文档后会发生什么？",
      "source_type": "chunk",
      "knowledge_base_id": "KB ID",
      "chunk_id": "chunk id",
      "title": "入门手册"
    }
  ]
}
```

## v0.6 Schema 变化

新增 `chat_sessions`：

```json
{
  "knowledge_base_id": "KB ID",
  "title": "会话标题",
  "is_pinned": false,
  "settings": {
    "mode": "hybrid",
    "top_k": 10,
    "enable_rerank": false,
    "enable_query_rewrite": false
  }
}
```

新增 `chat_messages`，assistant 消息会保存：

```json
{
  "role": "assistant",
  "content": "回答正文",
  "original_query": "用户原问题",
  "rewritten_query": "改写后的检索 query",
  "sources": [],
  "retrieval_trace": {
    "original_query": "用户原问题",
    "rewritten_query": "改写后的检索 query",
    "rewrite_enabled": true,
    "rewrite_failed": false,
    "rewrite_skipped": false,
    "retrieval_mode": "hybrid",
    "top_k": 10,
    "enable_rerank": false,
    "hit_count": 3
  },
  "model_config": {
    "qa_model_id": "KnowledgeQA 模型 ID",
    "embedding_model_id": "Embedding 模型 ID"
  }
}
```

`model_config` 只保存模型 id、name、type、provider、model_name 等非敏感信息，不保存 API Key。

## v0.3 / v0.3.1 Schema 变化

`KnowledgeBaseCreate` 新增必填字段：

```json
{
  "embedding_model_id": "Embedding 模型 ID",
  "summary_model_id": "KnowledgeQA 模型 ID"
}
```

`KnowledgeBaseRead` 返回：

```json
{
  "embedding_model_id": "...",
  "summary_model_id": "..."
}
```

`QuickAnswerResponse.sources[]` 保持兼容，并允许包含：

```json
{
  "chunk_id": "...",
  "score": 0.92,
  "chunk_type": "child",
  "parent_chunk_id": "...",
  "context_header": "...",
  "retrieval_method": "hybrid",
  "vector_score": 0.88,
  "keyword_score": 0.6,
  "rrf_score": 0.0149,
  "rerank_score": null,
  "context_chunk_id": "parent chunk id when expanded",
  "context_content": "parent chunk content when expanded"
}
```

`context_content` 是 v0.3.1 新增的可选字段；不影响旧客户端读取已有 sources 字段。

`RetrievalConfigSchema` v0.3 关键字段：

```json
{
  "retrieval_mode": "hybrid",
  "embedding_top_k": 50,
  "vector_threshold": 0.15,
  "keyword_threshold": 0.3,
  "rerank_top_k": 10,
  "rerank_threshold": 0.2,
  "rerank_model_id": null,
  "enable_rerank": false,
  "rrf_k": 60,
  "rrf_vector_weight": 0.7,
  "rrf_keyword_weight": 0.3
}
```

`KnowledgeSearchResponse`：

```json
{
  "hits": [
    {
      "document_id": "...",
      "chunk_id": "...",
      "content": "...",
      "retrieval_method": "keyword",
      "score": 0.75
    }
  ]
}
```

## 项目结构

```text
app/
  api/v1/              FastAPI 路由
  core/                配置和安全工具
  db/                  SQLAlchemy models、session、repository
  integrations/        OpenAI-compatible client、Qdrant store
  rag/                 parser、chunker、prompt、quick-answer、retriever
  schemas/             Pydantic schemas
  services/            应用服务层
  workers/             Celery app 和任务
frontend/              Vue 3 + TypeScript Dashboard
alembic/               数据库迁移
tests/                 pytest 测试
storage/               本地上传文件目录
```

## 验证命令

```powershell
python -m pytest -q
ruff check .
python -m compileall app tests
npm --prefix frontend run build
```

最近一次本地验证结果：

- `python -m pytest tests/test_v071_document_lifecycle.py tests/test_frontend_v071_document_lifecycle.py -q`：`5 passed`
- `python -m pytest tests/test_v071_chat_generation_lifecycle.py tests/test_frontend_v071_chat_generation_lifecycle.py -q`：`4 passed`
- `python -m pytest tests/test_v071_observability_status.py tests/test_frontend_v071_observability_status.py -q`：`3 passed`
- `python -m pytest tests/test_frontend_v071_command_palette.py -q`：`1 passed`
- `python -m pytest tests/test_v05_document_management.py::test_deleted_duplicate_file_can_be_uploaded_again tests/test_v05_document_management.py::test_active_duplicate_file_upload_returns_chinese_error -q`：`2 passed`
- `ruff check app\api\v1\documents.py app\db\repositories\document.py app\services\document.py tests\test_v05_document_management.py`：通过
- `python -m compileall app tests`：通过
- `npm --prefix frontend run build`：通过，仍有 Vite 大 chunk 提示。
- v0.71 分项验收详见 [CHANGELOG.md](CHANGELOG.md) 的 v0.71 Verification。

## 开发备注

- v0.71 仍默认单租户，`DEFAULT_TENANT_ID=10000`。
- Docker Compose 当前只提供 `postgres / redis / qdrant`，API、worker、前端 dev server 需要本地命令启动。
- 文档上传后必须启动 Celery Worker，否则文档会停留在 `pending` 或 `processing`。
- 切换 embedding 模型、维度、切分参数或 keyword 检索文本策略后，需要重处理文档或重建知识库来刷新 Qdrant 向量和 `chunks.search_text`。
- v0.3 keyword search 是 PostgreSQL FTS + 应用层 `jieba` 分词，不是完整 BM25；真正 BM25 引擎留到后续版本。
- Rerank 默认关闭；启用时必须先创建可用的 `Rerank` 模型，并在检索配置中绑定 `rerank_model_id`。
- 当前 OCR / MinerU 未接入，图片类文件会明确显示 unsupported/unavailable。
- 模型测试会透传 provider 的真实错误，例如认证失败、模型不存在、维度不匹配等，前端会渲染中文可读文本，不渲染 `[object Object]`。
- 生产部署前需要更换默认数据库密码，固定并妥善保存 `MODEL_CONFIG_ENCRYPTION_KEY`，并增加鉴权和访问控制。

## 版本记录

见 [CHANGELOG.md](CHANGELOG.md)。
