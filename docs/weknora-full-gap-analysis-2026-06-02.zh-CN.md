# knowmate 与本地 WeKnora 全量差距基线

日期：2026-06-02

v0.8 更新：2026-06-03 已完成 TASK-025 到 TASK-045。本文件仍保留 2026-06-02 的全量差距基线定位，但 Quick Q&A P0/P1 中的 retrieval diagnostics、FAQ import progress、chunk 管理、message search、model provider presets、vector-store types、composite retriever、OpenSearch sparse MVP、runtime status 真实化和附件上下文已在 v0.8 落地。

对比范围：

- knowmate：`D:\myproject\knowmate-agentic-rag`，commit `a97bb47`
- WeKnora：`D:\myproject\_references\WeKnora`，`VERSION=0.6.0`，commit `e352721`

本文件基于本地源码静态对比，是后续继续复刻 Tencent/WeKnora 时使用的全量差距基线。当前 Quick Q&A 主链路见 `docs/quick-answer-weknora-aligned-chain-2026-06-10.zh-CN.md`，v0.9 固定主链路设计备忘见 `docs/v0.9.md`。

## 总结结论

knowmate 当前已经覆盖 WeKnora Quick Q&A 的核心闭环：

```text
模型配置
  -> 知识库创建
  -> 文档/FAQ 导入
  -> parser registry
  -> adaptive chunking
  -> PostgreSQL chunk metadata
  -> Qdrant dense vector
  -> keyword / vector / hybrid 检索
  -> retrieval diagnostics / rerank cleaning / FAQ boost
  -> Quick Answer / Chat stream
  -> answer + sources + trace + rendered context
  -> chunk 管理 / generated questions
  -> message search / attachment context
```

但 knowmate 仍是“单租户 Quick Q&A 工作台”。WeKnora v0.6.0 已是完整知识平台，覆盖账号租户、RBAC、组织共享、Agent、MCP、Wiki、图谱、外部数据源、IM、多向量库、对象存储、DocReader/MinerU、CLI/MCP server、Chrome 插件、小程序和 Langfuse。

因此后续不应把差距理解成“每个 WeKnora 模块都立即补齐”。更合理的路线是：

1. 先把 Quick Q&A 质量、可解释性和管理闭环补到 WeKnora Lite 水平。
2. 再补 Auth/RBAC-lite，使后续 per-user pin、favorites、tenant 成员和审计有承载。
3. 最后按 WeKnora 的平台边界增量引入 Agent、Wiki、DataSource、IM、CLI/MCP server 等大模块。

## 源码证据快照

| 项目 | knowmate | WeKnora | 说明 |
| --- | --- | --- | --- |
| 后端技术栈 | FastAPI / SQLAlchemy / Celery | Go / Gin / GORM / Asynq | 技术栈不同是预期差异 |
| API 路由注册 | `app/api/v1/router.py` 注册 17 个 router | `internal/router/router.go` 注册 30+ 组 Register*Routes | WeKnora 平台面仍明显更大 |
| API endpoint 粗略数量 | `rg @(router).(get/post/put/delete/patch)` 约 82 条 | `rg .(GET/POST/PUT/DELETE/PATCH)` 约 285 条 | 仅静态粗计，含辅助路由 |
| ORM 表模型 | `app/db/models.py` 14 张表 | `migrations/sqlite/000000_init.up.sql` 30 张表 | WeKnora 还含 auth、RBAC、Agent、Wiki、DataSource 等 |
| 迁移数量 | Alembic 16 个 | versioned SQL up/down 58 组，116 文件 | knowmate schema 仍是 Quick Q&A 子集 |
| 前端视图 | `frontend/src/views` 9 个页面文件 | `frontend/src/views` 77 个页面/组件文件 | WeKnora 是完整平台 shell |
| 前端 store | 5 个 store | 7 个 store + 更完整 API/client 层 | WeKnora 有 auth、organization、settings、ui 等 |
| RAG pipeline | `app/services/quick_answer.py` 线性 prepare/search/answer | `internal/application/service/chat_pipeline/*` 插件链 | WeKnora 包含 query understand、parallel search、FAQ merge、web fetch、wiki boost |
| Parser | `app/rag/parser.py` builtin + OCR 占位 | `internal/infrastructure/docparser/*` + `docreader/parser/*` | WeKnora 有 DocReader、MinerU、WeKnoraCloud、image resolver |
| Chunker | `app/rag/chunker.py` 已复刻 adaptive tier | `internal/infrastructure/chunker/*` | 方向接近，但 WeKnora 测试与诊断更完整 |
| Vector store | Qdrant 可用，OpenSearch/Elasticsearch sparse MVP 和 provider types 元数据 | `internal/types/vectorstore.go` 多 engine | WeKnora 支持 ES/Milvus/Weaviate/Doris/Tencent/OpenSearch 等，knowmate 仍未接生产级多 store |

## 复刻等级定义

| 等级 | 含义 |
| --- | --- |
| 已复刻 | 已有可用 API、数据模型、前端入口或主链路行为 |
| 部分复刻 | 概念存在，但 WeKnora 的完整交互、边界、后端能力或平台约束缺失 |
| 未复刻 | 当前仓库基本没有对应模块 |
| 暂不建议 | 属于 WeKnora 平台能力，但会冲击 v1 Quick Q&A 主线，应延后 |

## 模块差距总表

| 模块 | knowmate 当前状态 | WeKnora v0.6.0 状态 | 复刻等级 | 建议优先级 |
| --- | --- | --- | --- | --- |
| 模型配置 | OpenAI-compatible 模型 CRUD、凭据加密、KB 绑定 | 内置模型、provider 管理、Ollama、WeKnoraCloud、VLM/ASR/rerank check、managed_by/display_name | 部分复刻 | P0/P1 |
| 知识库 | document/faq、capabilities、pin、settings、vector_store_id | document/faq/wiki、creator_id、copy、move target、share、storage/vector/wiki/graph/advanced settings | 部分复刻 | P0/P1 |
| 文档管理 | 上传、URL、手动文本、预览、下载、取消、移动、spans、重处理 | 文件/URL/manual、batch、download、preview、cancel、move progress、image update、pending subtasks | 部分复刻 | P0 |
| FAQ | CRUD、导入导出、相似问法、索引模式、标签、import progress、last result、字段批量更新、FAQ boost | 批量 upsert、similar questions、字段批量更新、import progress、last result display | 部分复刻 | P1 |
| Chunk | list by document、preview、parent-child metadata、by-id、update/disable、generated questions、debug/token 诊断 | chunk CRUD、by-id、删除 generated question、image/video info、question generation | 部分复刻 | P1 |
| 检索 | Qdrant dense、PG keyword、hybrid RRF、parent-child、rerank cleaning/MMR、FAQ merge、composite retriever、OpenSearch sparse MVP | composite retriever、多 engine、env store + DB store、parallel search、FAQ merge、wiki boost、GraphRAG/Web Search | 部分复刻 | P1/P2 |
| Quick Answer / Chat | sessions、messages、stream、stop、auto title、sources、trace、mention scope、rendered_context、history merge、message search、文本附件上下文 | knowledge-qa、agent-qa、continue-stream、message search、attachments、images、rendered_content、agent steps | 部分复刻 | P1 |
| Parser | builtin txt/md/pdf/docx/csv/json/xlsx、OCR 占位 | DocReader gRPC/HTTP、simple、MinerU、MinerU Cloud、WeKnoraCloud、image/audio 多模态 | 部分复刻 | P1/P2 |
| Chunker | auto/heading/heuristic/legacy、protected blocks、diagnostics、parent-child | adaptive 3-tier、token-aware、validator、debug UI、测试覆盖更全 | 部分复刻 | P0/P1 |
| 存储 | 本地文件、下载/预览闭环 | local/MinIO/COS/TOS/S3/OSS/KS3/OBS、presigned URL、storage status/check | 小部分复刻 | P1/P2 |
| Vector Store | Qdrant registry、types 元数据、OpenSearch/Elasticsearch sparse MVP、配置屏蔽敏感字段 | Qdrant/ES/Milvus/Weaviate/Doris/Tencent/OpenSearch/env stores、多 store fan-out | 部分复刻 | P1/P2 |
| Auth / Tenant / RBAC | 默认单租户 `10000`，无登录 | login/register/auto-setup/OIDC、tenant member、Owner/Admin/Contributor/Viewer、audit | 未复刻 | P1 |
| Organization / Share | 无 | organization、join request、KB share、Agent share、shared KB/Agent | 未复刻 | P2 |
| User preferences / Favorites | tenant 级 pin | per-user KB pin、favorites、user preferences、system admin | 未复刻 | P1/P2 |
| Agent / MCP / Skills | 无 | Agent CRUD、agent stream、MCP services、tool approvals、skills、sandbox | 未复刻 | P3 |
| Wiki / Graph | indexing flag 占位 | wiki pages、graph、stats、lint、auto-fix、wiki log、GraphRAG | 未复刻 | P3 |
| DataSource | URL 导入 | Feishu/Notion/Yuque connector、sync logs、resource browse、credentials | 未复刻 | P3 |
| Web Search | 无 | provider CRUD/test、DuckDuckGo/Bing/Google/Tavily/Baidu/Ollama/SearXNG | 未复刻 | P2/P3 |
| IM / 多端入口 | 无 | WeCom/Feishu/Slack/Telegram/DingTalk/Mattermost/WeChat、小程序、Chrome 插件 | 未复刻 | P3 |
| CLI / MCP server | 无 | `weknora` CLI、MCP server、ClawHub skill | 未复刻 | P3 |
| Evaluation | 无 | evaluation API、dataset、retrieval/generation metrics | 未复刻 | P2/P3 |
| 可观测性 | runtime-status、processing spans、retrieval trace | Langfuse tracing、task queue/dead letter、audit log、pipeline tracing | 部分复刻 | P1 |

## 后端 API 差距

### knowmate 已有 API 面

当前 `app/api/v1/router.py` 注册：

- `/chat-sessions`
- `/messages`
- `/knowledge-bases`
- `/knowledge-bases/{kb_id}/faqs`
- `/knowledge-bases/{kb_id}/tags`
- `/knowledge-search`
- `/documents`
- `/chunks`
- `/quick-answer`
- `/model-config`
- `/models`
- `/retrieval-config`
- `/runtime-status`
- `/chunker`
- `/parser-engines`
- `/tasks`
- `/vector-stores`

这些 API 已经支撑 v1 Quick Q&A 主线，并在 v0.8 补齐了 retrieval diagnostics、FAQ import progress、chunk 管理、message search、provider/types 元数据、runtime status 和附件上下文相关接口。

### WeKnora 多出的 API 面

`internal/router/router.go` 还注册以下主要路由组：

- Auth：register、login、auto-setup、OIDC、refresh、validate、logout、me、preferences、change-password。
- Tenant/RBAC：tenant CRUD、members、invitations、invite links、audit-log、cross-tenant search。
- Organization：organization CRUD、join request、member management、KB/Agent share、shared resources。
- Knowledge advanced：batch、clear contents、copy KB、move targets、move progress、image info update。
- Chunk advanced：chunk by id、update/delete chunk、delete generated question。
- FAQ advanced：batch upsert、fields batch update、import progress、last-result display status。
- Session/Message：message search、chat-history stats、clear messages、generate title、stop、pin/unpin、continue-stream。
- Chat：`/chat/knowledge/:session_id` 和 `/chat/agent/:session_id`。
- Initialization/System：KB config initialize/update、Ollama、remote model check、embedding/rerank/asr/multimodal checks、parser/storage engine check。
- MCP/Agent/Skill：MCP service CRUD/test/tool approvals、agent CRUD/copy/suggested questions、skills list。
- Web Search：provider types、provider CRUD/test。
- Vector Store：store types、raw test、CRUD、by-id test。
- DataSource：connector types、credential validation、sync/pause/resume/logs/resources。
- WeKnoraCloud：credentials、status。
- Wiki：pages、index、log、graph、stats、search、rebuild-links、lint、auto-fix、issues。
- Files：authenticated file proxy、presigned file URL、presigned preview。
- IM：callback、channel CRUD/toggle、WeChat QR login。

### API 复刻建议

v0.8 已完成原 P0 Quick Q&A 缺口：

1. FAQ import progress / last result / display status。
2. chunk by id、chunk update/disable、generated question 管理边界。
3. message search 和 chat-history stats 轻量版。
4. vector-stores `/types`、model providers 和 parser/storage/model/vector status 真实返回。

P1 建平台底座：

1. Auth auto-setup + login。
2. Tenant member + role 字段。
3. 审计日志最小版。
4. per-user KB pin / favorites。

P2 以后再上 Agent/Wiki/DataSource/Web Search。

## 数据模型差距

### knowmate 当前表

`app/db/models.py` 当前 14 张表：

- `tenants`
- `knowledge_bases`
- `knowledge_base_pins`
- `knowledge_tags`
- `knowledge_processing_spans`
- `model_configs`
- `vector_stores`
- `chat_sessions`
- `chat_messages`
- `knowledges`
- `processing_tasks`
- `faq_entries`
- `faq_import_results`
- `chunks`

### WeKnora 当前表

`migrations/sqlite/000000_init.up.sql` 初始化表 30 张：

- Quick Q&A 核心：`tenants`、`models`、`knowledge_bases`、`knowledges`、`sessions`、`messages`、`chunks`。
- Auth/RBAC：`users`、`auth_tokens`、`tenant_members`、`tenant_invitations`、`audit_logs`。
- 用户状态：`user_resource_favorites`、`user_kb_pins`。
- 知识管理：`knowledge_tags`、`vector_stores`。
- Agent/MCP：`custom_agents`、`mcp_services`、`mcp_tool_approvals`。
- 组织共享：`organizations`、`organization_tenant_members`、`kb_shares`、`agent_shares`、`organization_join_requests`、`tenant_disabled_shared_agents`。
- IM：`im_channels`、`im_channel_sessions`。
- 数据源/搜索：`data_sources`、`sync_logs`、`web_search_providers`。

versioned migration 还包括：

- `wiki_pages`、`wiki_page_issues`、`wiki_log_entries`。
- `task_pending_ops`、`task_dead_letters`。
- `system_settings`。
- `knowledge_processing_spans`。
- `pending_subtasks_count`。
- `models.display_name`。

### 关键字段差距

| 表/实体 | knowmate | WeKnora | 差距影响 |
| --- | --- | --- | --- |
| KnowledgeBase | 无 `creator_id`，pin 按 tenant | 有 `creator_id`，pin 由 `user_kb_pins` 计算 | 无法实现 Contributor 只能管理自己 KB 的规则 |
| KnowledgeBase config | chunking/parser/faq/indexing/vector_store | 另有 image/vlm/asr/storage/question_generation/wiki/extract | 高级解析、多模态、图谱和存储 provider 无承载 |
| ChatSession | tenant、kb、title、pin、settings | user_id、agent_id、last_request_state、channel/continue-stream 相关状态 | 多用户、Agent、IM 和恢复流能力不足 |
| ChatMessage | content、sources、trace、model_config、status | request_id、references、agent_steps、mentioned_items、images、attachments、rendered_content、channel、knowledge_id | 附件、Agent 展示、历史检索和上下文恢复不足 |
| Knowledge | file metadata、parse_status、tag、spans | channel、summary、pending_subtasks_count、image/audio/multimodal metadata | 高级任务编排和多端来源不足 |
| Chunk | parent-child、context_header、images | image_info、video_info、generated questions、full chunk CRUD | 多模态来源展示和问题生成不足 |
| Model | `model_configs` 混合保存 provider/base_url/api key/model names | WeKnora `models` 类型更通用，credential subresource，managed_by/display_name | provider preset、内置模型和不同模型类型管理不足 |
| VectorStore | provider + config_json，目前只支持 qdrant | engine_type + connection_config + index_config + env/user/shared/unavailable source | 多向量库、fan-out 和跨租户共享不足 |

## RAG 主链路差距

### knowmate 当前链路

```text
QuickAnswerService.prepare_answer
  -> optional query rewrite
  -> KnowledgeSearchService.search
  -> vector / keyword / hybrid + optional rerank
  -> source payloads
  -> build_quick_answer_messages
  -> OpenAI-compatible chat completion / stream
  -> ChatMessage persistence
```

### WeKnora 链路

`internal/application/service/chat_pipeline/*` 拆成插件式 pipeline：

- `load_history`
- `query_understand`
- `query_expansion`
- `extract_entity`
- `search_parallel`
- `search_entity`
- `merge`
- `merge_faq`
- `merge_history`
- `merge_expand`
- `merge_overlap`
- `filter_top_k`
- `rerank`
- `rerank_clean`
- `wiki_boost`
- `web_fetch`
- `memory`
- `chat_completion`
- `chat_completion_stream`
- `into_chat_message`
- `data_analysis`

### 当前差距

knowmate 的链路清晰、适合 v1，但相比 WeKnora：

- 缺 query understand / intent 分类。
- 缺 query expansion。
- 缺实体抽取和实体检索。
- 已有 composite retriever diagnostics，但缺真正多生产后端 parallel search 和 env store + DB store 完整 fan-out。
- 已有 FAQ merge / boost 轻量策略，但缺 WeKnora 完整 wiki/web/graph boost 链。
- 已有 history merge / rendered_context / prompt_context_summary，但缺完整 query understand pipeline。
- 缺 web fetch/search 融合。
- 缺 wiki boost / graph retrieval。
- 已有分阶段 retrieval diagnostics，但缺完整 pipeline 插件化和 Langfuse 级 trace。

### 建议

短期不要直接重写成 WeKnora chat_pipeline。更稳妥的做法：

1. 保持 `QuickAnswerService` 线性结构。
2. 继续把 v0.8 的 composite retriever 扩展为可插拔多后端，但每次只接一个真实 provider。
3. 在引入 Web Search/Wiki/Graph 前，先补 Auth/RBAC-lite 和审计，避免检索范围失控。
4. 再将 search 过程拆成更稳定的小 service，给 future pipeline 留入口。

## Parser / Chunker 差距

### Parser

knowmate：

- builtin 支持 `txt`、`md`、`pdf`、`docx`、`csv`、`json`、`xlsx`。
- `ocr` engine 只是不可用占位。
- KB 可以配置 parser engine rules。

WeKnora：

- `internal/infrastructure/docparser/engine_registry.go`
- `grpc_parser.go`、`http_parser.go`
- `mineru_converter.go`、`mineru_cloud_converter.go`
- `weknoracloud_http_reader.go`
- `image_resolver.go`
- `docreader/parser/*` 支持 doc/docx/excel/image/markdown/pdf/web/markitdown/chain parser。

差距：

- 缺 DocReader 远程解析服务。
- 缺 MinerU / MinerU Cloud。
- 缺 WeKnoraCloud parser。
- 缺 image resolver、远程图片拉取和安全处理。
- 缺图片/VLM、音频/ASR。
- 缺 parser check/reconnect 的真实管理面。

### Chunker

knowmate 已复刻：

- `auto -> heading -> heuristic -> legacy`。
- protected blocks：公式、图片、markdown link、表格、代码块。
- doc profile。
- validator。
- parent-child。
- preview diagnostics。

WeKnora 更完整：

- 独立 `internal/infrastructure/chunker/*`，包含 profiler、strategy、validator、tokens、heading hierarchy、header tracker。
- 测试覆盖更细，包括 token limit、pattern、heading/heuristic splitter。
- 前端 KBChunkingDebug 更成熟。

差距：

- knowmate token 估算仍较简化。
- v0.8 已补 chunk diagnostics 前端统计、rejected tiers、profile 展示和 token-aware validation，但仍不如 WeKnora 完整。
- v0.8 已补 generated questions 数据结构和手工管理 API，但未做自动 question generation pipeline。
- 多模态 chunk 的 image/video/formula metadata 不完整。

建议：

1. P1：继续收敛 token 估算与 WeKnora token-aware validator 的差异。
2. P1：增加 generated question 自动生成 pipeline，但必须显式配置模型，不做静默 fallback。
3. P2：多模态 chunk metadata。

## 检索与索引差距

knowmate：

- Qdrant dense vector。
- PostgreSQL `chunks.search_text` keyword fallback。
- hybrid RRF。
- parent-child：child match，parent/context return。
- optional rerank service，支持 passage cleaning、失败降级、阈值降级和 MMR。
- v0.8 composite retriever diagnostics 和 OpenSearch/Elasticsearch sparse MVP。

WeKnora：

- Retriever registry + composite retriever。
- Env stores + DB-managed stores。
- Elasticsearch、Qdrant、Milvus、Weaviate、Doris、Tencent VectorDB、OpenSearch。
- Postgres/SQLite env fallback。
- 多 KB 跨 vector store fan-out。
- BM25/sparse 真实后端。
- Wiki boost、GraphRAG、Web Search 融合。

差距：

- 非 Qdrant provider 仍未完成生产级连接、索引创建和真实集群 smoke。
- KB 绑定 vector store 后仍没有完整多 store fan-out。
- 默认 keyword 检索主要依赖 Postgres 文本匹配，不是 WeKnora 式生产级多后端 sparse/BM25。
- v0.8 已有 retriever diagnostics，但还没有 WeKnora 完整 parallel search 和 shared KB 场景下的 vector store metadata 隐藏逻辑。

建议：

1. P1：补 OpenSearch/Elasticsearch 真实集群配置、索引创建、健康检查和 smoke 测试。
2. P1：让 KB 绑定的 vector store 真正参与 composite retriever，而不是只保留默认 qdrant + keyword。
3. P2：再按 WeKnora 边界扩展 Milvus、Weaviate、Doris、Tencent VectorDB 等 provider。
4. P2：补 shared KB 场景下的 vector store metadata 隐藏逻辑。

## 模型管理差距

knowmate 已有：

- `model_configs` 和 `/models`。
- `/models/providers` provider presets。
- KnowledgeQA、Embedding、Rerank 类型边界。
- OpenAI-compatible runtime config。
- 凭据加密和 last4 显示。

WeKnora 多出：

- provider list。
- builtin models yaml。
- Ollama 状态、模型列表、下载任务。
- WeKnoraCloud status/credentials。
- remote/embedding/rerank/asr/multimodal check。
- `managed_by`、`display_name`。
- VLM、ASR、rerank 多 provider。

建议：

1. P1：把 v0.8 provider presets 扩展为可管理 provider 目录，但仍保存 OpenAI-compatible 连接。
2. P1：增加远程模型检查、embedding/rerank/asr/multimodal check 的兼容形状。
3. P1：增加 rerank 绑定到 KB/retrieval config 的完整 UI。
4. P2：Ollama / WeKnoraCloud / VLM / ASR。

## 前端差距

### knowmate 当前信息架构

- `/#/chat`
- `/#/knowledge-bases`
- `/#/knowledge-bases/:kbId`
- `/#/knowledge-bases/:kbId/documents`
- `/#/knowledge-bases/:kbId/faqs`
- `/#/settings`

### WeKnora 信息架构

- `/login`
- `/register`
- `/join`
- `/platform/settings`
- `/platform/knowledge-bases`
- `/platform/knowledge-bases/:kbId`
- `/platform/agents`
- `/platform/creatChat`
- `/platform/knowledge-bases/:kbId/creatChat`
- `/platform/chat/:chatid`
- `/platform/organizations`
- dev markdown test page

### 前端模块差距

| 区域 | knowmate | WeKnora | 建议 |
| --- | --- | --- | --- |
| 平台 shell | 简洁 sidebar | platform shell、tenant selector、user menu、global invite、command palette | P1 做登录后 shell |
| Chat | Quick Q&A、mentions、sources、trace、stop | Agent/normal mode、attachments、images、tool results、thinking、continue stream、message search | P0/P1 补附件和 message search |
| KB detail | 已有 detail shell、documents/FAQ/settings | KnowledgeBase.vue 聚合文档、FAQ、Wiki、settings、share、data source | P0 保持并增强 tab 密度 |
| Settings | model/vector/retrieval/parser/storage/system 状态 | General、Models、Ollama、Parser、Storage、Retrieval、MCP、Web Search、Tenant、System、API、Chat History | P1 增加真实 sections |
| Components | 6 个核心组件 | 大量业务组件、tool result renderer、KB settings 组件 | 按需求增量引入，不做大重构 |
| i18n | 中文工作台文案 | zh/en/ko/ru locales | P2 再考虑 |

## 安全与权限差距

knowmate：

- 单租户开发，`DEFAULT_TENANT_ID=10000`。
- 模型 API key 加密或遮蔽。
- 无登录、无用户、无 RBAC、无审计。

WeKnora：

- 登录/注册/邀请/OIDC。
- Tenant member：Owner / Admin / Contributor / Viewer。
- KB ownership：Contributor 管理自己创建的 KB，Admin/Owner 管理全局。
- 系统管理员。
- 租户审计日志和系统审计日志。
- API Key、MCP/DataSource credentials AES-GCM。
- docreader gRPC TLS + Token。
- SSRF 防护和存储路径 tenant 校验。
- Agent sandbox。

建议：

1. P1 建 Auth/RBAC-lite，不要等 Agent/Wiki 后再补。
2. 先保持 `DEFAULT_TENANT_ID=10000` 自动迁移为默认 tenant。
3. 新增 `users`、`tenant_members`、`audit_logs`、`user_kb_pins`，把现有 tenant pin 迁移到默认用户。
4. API handler 加 dependency，但业务权限逻辑放 service/repository。
5. 前端新增 login/auto-setup，不影响开发单租户快速启动。

## WeKnora 大模块未复刻清单

以下模块属于完整平台范围，不建议和 v1 Quick Q&A 主线混在一个版本：

- Agent Mode：custom agents、agent type presets、ReAct、tool calls、agent steps、suggested questions。
- MCP：MCP service CRUD、tool/resource discovery、tool approval、人机审批。
- Skills：内置 skills、sandbox、技能运行。
- Wiki：wiki pages、index、log、graph、stats、lint、auto-fix、issues。
- Knowledge Graph：entity/relation extraction、GraphRAG、Neo4j。
- DataSource：Feishu、Notion、Yuque，sync cursor/logs/resources。
- Web Search：provider CRUD/test，web fetch/search 融合。
- IM：WeCom、Feishu、Slack、Telegram、DingTalk、Mattermost、WeChat。
- 多端：CLI、MCP server、Chrome Extension、小程序、desktop/Wails。
- Evaluation：dataset、retrieval metrics、generation metrics。
- Langfuse：LLM/tool/pipeline trace。
- 对象存储：MinIO/COS/TOS/S3/OSS/KS3/OBS 和 presigned URL。
- 高级解析：DocReader、MinerU、WeKnoraCloud parser、VLM、ASR。

## 推荐路线图

### P0：Quick Q&A 完整度继续补齐

目标：不扩大到 Agent/Wiki/RBAC 全平台，先让现有主链路更接近 WeKnora Lite。

v0.8 已完成：

1. FAQ import progress、last import result、display status。
2. Chunk by id、chunk update/disable、delete generated question API 兼容边界。
3. Retrieval trace 拆分到 vector/keyword/RRF/parent/rerank。
4. Chunk debug UI 补 profile、rejected tiers、size stats 和 token-aware validation。
5. Message search 轻量版和 chat-history stats。
6. Settings 接入真实 parser/storage/model/vector status。

### P1：平台底座

目标：为 WeKnora 式多用户和可追溯操作铺底。

1. Auth auto-setup + login。
2. users、tenant_members、roles。
3. KB `creator_id`。
4. per-user `user_kb_pins` 和 favorites。
5. audit_logs 最小版。
6. model providers preset。已在 v0.8 落地，后续需补 provider 管理和远程模型检查。
7. attachment context MVP。文本附件已在 v0.8 落地，后续再补图片/文件持久化和权限边界。
8. storage provider config 形状，但仅 local 可用。

### P2：检索与集成扩展

目标：增强可替换性，但仍不进入完整 Agent。

1. vector store `/types` 兼容 WeKnora，其他 provider unavailable。已在 v0.8 落地，后续补 provider 实际接入。
2. OpenSearch/Elasticsearch 作为真实 BM25/sparse 后端。v0.8 已完成 MVP/fake-client 边界，后续补真实集群 smoke。
3. composite retriever 接口。已在 v0.8 落地，后续补生产级 fan-out。
4. Web Search provider 设置和测试。
5. Mermaid 安全渲染。
6. Evaluation MVP。

### P3：平台大模块

目标：按 WeKnora 模块边界逐步复刻。

1. Agent Mode MVP。
2. MCP service + tool approval。
3. Wiki Mode MVP。
4. DataSource connector。
5. IM channels。
6. CLI / MCP server。
7. Langfuse tracing。
8. DocReader/MinerU/WeKnoraCloud parser。

## 不建议近期做的事

- 不要把 `QuickAnswerService` 一次性重写成完整 WeKnora chat_pipeline。
- 不要在没有 Auth/RBAC 前实现复杂 organization/share。
- 不要为了“多 vector store”同时接入所有引擎；先做接口和一个真实新增后端。
- 不要把 OCR/MinerU 写成静默本地 fallback；生产缺配置必须给清晰错误。
- 不要让前端变成营销页；继续保持中文工作台。
- 不要在 API 响应或页面回显 API key 明文。

## 下一轮最小任务包建议

如果继续按 WeKnora 对齐推进，建议下一轮只做一个小版本：

```text
v0.9 候选：Auth/RBAC-lite 与单租户到多用户底座过渡

TASK-046 Auth auto-setup + login 最小闭环
TASK-047 users / tenant_members / roles schema
TASK-048 KB creator_id / ownership 边界
TASK-049 audit_logs 最小版
TASK-050 per-user pin / favorites
```

这个任务包仍然服务 v1 Quick Q&A，不提前引入 Agent/Wiki/DataSource，但会给后续 per-user scope、审计、共享和权限感知 UI 留出结构承载。

## 验证说明

本文件只做静态源码对比和文档更新，未修改应用代码，未运行后端或前端测试。

用于对比的主要命令包括：

- `rg --files`
- `git rev-parse --short HEAD`
- `rg "@(router|app)\.(get|post|put|delete|patch)" app/api/v1`
- `rg "\.(GET|POST|PUT|DELETE|PATCH)\(" internal/router/router.go`
- `rg "__tablename__" app/db/models.py`
- `rg "CREATE TABLE IF NOT EXISTS" migrations/sqlite/000000_init.up.sql`
- `Get-ChildItem frontend/src/views`
- `Get-ChildItem internal/application/service/chat_pipeline`
- `Get-ChildItem internal/infrastructure/docparser`
- `Get-ChildItem internal/infrastructure/chunker`
