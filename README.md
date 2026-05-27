# knowmate 知友

knowmate 知友是一个参考 [Tencent/WeKnora](https://github.com/Tencent/WeKnora) 核心思路实现的知识库 RAG 项目。后端技术栈从 WeKnora 的 Go 实现改为 Python / FastAPI；项目不是 Tencent/WeKnora 官方项目。

当前版本为 v0.3，主线仍聚焦 WeKnora-style Quick Q&A，并补齐 WeKnora 方向的 hybrid retrieval / knowledge search / rerank 边界：

```text
模型管理
  -> 知识库绑定 QA / Embedding 模型
  -> 文档上传
  -> Celery Worker 解析文档
  -> Adaptive Chunking 切片
  -> 生成 embedding
  -> chunk 元数据写 PostgreSQL
  -> 向量写 Qdrant
  -> quick-answer / knowledge-search
  -> vector + keyword 召回
  -> RRF hybrid merge
  -> optional rerank
  -> parent-child context expansion
  -> chat model 生成 answer
  -> 返回 answer + sources
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
- Vue 中文测试台：模型管理、解析切分设置、检索配置、知识库创建、文档上传、文档重处理、切片查看、knowledge-search、quick-answer 问答。
- 自动化测试：覆盖多模型 CRUD、凭据加密、知识库模型校验、重处理、检索配置、hybrid/RRF/rerank/parent-child retrieval、knowledge-search API、前端关键逻辑、API 和文档处理 payload。

暂未实现：

- 登录、RBAC、多租户隔离。
- OCR / MinerU / 图片类文件解析。
- 真正 BM25 引擎、pg_jieba、Elasticsearch/OpenSearch、ParadeDB/pg_search。
- GraphRAG、多维索引、query rewrite、多轮会话、流式回答。
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
| 前端 | Vue 3, Vite, lucide-vue-next |
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

Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 页面使用流程

1. 在“模型配置”里分别配置 QA 模型和 Embedding 模型。
2. QA 模型可选择 Qwen / DashScope、DeepSeek 或 OpenAI-compatible；Embedding 模型当前主要使用 Qwen / DashScope。
3. 填入 API Key 后点击“测试 QA”或“测试向量”。
4. 保存模型后，API Key 输入框会清空；再次测试会使用后端已加密保存的 Key。
5. 在绑定下拉框里选择 `KnowledgeQA` 和 `Embedding` 模型。
6. 在“解析与切分设置”里选择 parser engine 和 chunking strategy，可先点“切分预览”。
7. 创建知识库，知识库会绑定当前选择的 QA 和 Embedding 模型。
8. 上传 `.txt/.md/.pdf/.docx/.csv/.json/.xlsx` 文档。
9. 等待 Worker 处理到“解析完成”，页面展示 chunks。
10. 切换向量模型、维度或切分参数后，点击“重建文档”或“重建知识库”重建向量。
11. 在“检索配置”里选择 `hybrid / vector_only / keyword_only`，可调整 keyword 阈值、RRF 权重和 rerank 开关。
12. 在“知识搜索”里调试 sources，不调用 LLM。
13. 在“快速问答”里提问，返回回答和来源依据。

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
| `GET` | `/api/v1/knowledge-bases/{kb_id}/documents` | 查询知识库下文档列表 |
| `POST` | `/api/v1/knowledge-bases/{kb_id}/reprocess` | 批量重处理知识库文档 |
| `POST` | `/api/v1/knowledge-bases/{kb_id}/documents/file` | 上传文档 |
| `GET` | `/api/v1/documents/{document_id}` | 查询文档处理状态 |
| `DELETE` | `/api/v1/documents/{document_id}` | 软删除文档 |
| `GET` | `/api/v1/documents/{document_id}/chunks` | 查询文档切片 |
| `POST` | `/api/v1/documents/{document_id}/reprocess` | 重处理单个文档 |
| `POST` | `/api/v1/knowledge-search` | 知识搜索，只返回检索 hits，不调用 LLM |
| `POST` | `/api/v1/quick-answer` | 快速问答 |

## v0.3 Schema 变化

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
  "context_chunk_id": "parent chunk id when expanded"
}
```

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
frontend/              Vue 中文测试台
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

- `python -m pytest -q`：`44 passed`
- `ruff check .`：通过
- `python -m compileall app tests`：通过
- `npm --prefix frontend run build`：通过
- 浏览器自测：
  - Docker Compose `postgres / redis / qdrant` healthy。
  - `alembic upgrade head` 已升级到 `0005_v03_keyword_retrieval`。
  - API `/health` 返回 `{"status":"ok"}`。
  - Celery worker 已连接 Redis 并 ready。
  - Vite 工作台可访问 `http://127.0.0.1:5173`。

## 开发备注

- v0.3 默认单租户，`DEFAULT_TENANT_ID=10000`。
- Docker Compose 当前只提供 `postgres / redis / qdrant`，API、worker、前端 dev server 需要本地命令启动。
- 文档上传后必须启动 Celery Worker，否则文档会停留在 `pending` 或 `processing`。
- 切换 embedding 模型、维度、切分参数或 keyword 检索文本策略后，需要重处理文档或重建知识库来刷新 Qdrant 向量和 `chunks.search_text`。
- v0.3 keyword search 是 PostgreSQL FTS + 应用层 `jieba` 分词，不是完整 BM25；真正 BM25 引擎留到后续版本。
- Rerank 默认关闭；启用时必须先创建可用的 `Rerank` 模型，并在检索配置中绑定 `rerank_model_id`。
- 当前 OCR / MinerU 未接入，图片类文件会明确显示 unsupported/unavailable。
- 模型测试会透传 provider 的真实错误，例如认证失败、模型不存在、维度不匹配等，前端会渲染中文可读文本。
- 生产部署前需要更换默认数据库密码，固定并妥善保存 `MODEL_CONFIG_ENCRYPTION_KEY`，并增加鉴权和访问控制。

## 版本记录

见 [CHANGELOG.md](CHANGELOG.md)。
