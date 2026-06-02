# knowmate 与本地 WeKnora 复刻差距对比及 v0.7 任务建议

日期：2026-05-31

2026-06-02 更新：已基于 `D:\myproject\_references\WeKnora` 本地 `VERSION=0.6.0`、commit `e352721` 和迁移 `000057_models_display_name` 重新对照。v0.71 的完成归档已独立整理到 `docs/weknora-local-comparison-v0.71-roadmap.zh-CN.md`。本文件保留 v0.7 归档语境。

状态更新：2026-06-01 已按本文 P0 建议完成 knowmate v0.7。TASK-010 到 TASK-019 已落地，覆盖 KB capabilities / pin、KB 详情一体化设置、多知识库/文件范围检索、Chat mention、文档处理 timeline、FAQ 相似问法和 FAQ 索引模式。2026-06-02 已继续完成 v0.71 P0 操作闭环与可观测性任务包。

对比范围：

- knowmate：`D:\myproject\knowmate-agentic-rag`
- WeKnora 参考源码：`D:\myproject\_references\WeKnora`

本报告基于本地源码静态对比，不包含浏览器逐页点击验收。对比重点是 v1 Quick Q&A 主线、前端可见工作流，以及决定 knowmate v0.7 是否继续补齐的核心能力。

## 结论摘要

knowmate v0.7 已经复刻了 WeKnora Quick Q&A 的主干：模型配置、知识库、文档/FAQ、解析注册表、自适应切分、Qdrant 向量、keyword/hybrid 检索、parent-child、可选 rerank、会话化问答、流式回答、sources/trace、标签、FAQ 导入导出、文档预览、设置中心外壳、KB capabilities / pin、KB 详情一体化设置、多 scope 检索、Chat mention、文档处理 timeline、FAQ 相似问法和 FAQ 索引模式。

但它仍然是“单租户 Quick Q&A 工作台”，不是完整 WeKnora 平台。和本地 WeKnora 相比，最大的未复刻区域是：

- 平台外壳：登录、初始化、租户/组织、RBAC、审计、用户收藏、API Key。
- Chat 体验：knowmate v0.7 已补多知识库/文件 scope 和 Chat mention；WeKnora 仍多出附件、图片、Agent Mode、Web Search、MCP 工具和工具调用可视化。
- 知识库能力：knowmate v0.7 已补 KB capabilities / pin、详情设置、FAQ 相似问法和 FAQ 索引模式；WeKnora 仍多出 Wiki 类型、共享、复制/移动、Graph 设置和更完整批量操作。
- 文档处理：WeKnora 有 DocReader、MinerU、WeKnoraCloud、高级 OCR/VLM/ASR、对象存储、预签名文件、解析阶段 trace；knowmate 只做本地基础解析和简化 preview。
- 检索与索引：WeKnora 支持多向量/检索后端、外部 sparse/BM25 类型后端、fan-out/composite retrieve、Web Search 融合、知识图谱/Wiki boost；knowmate 主要是 Qdrant + PostgreSQL FTS fallback。
- 前端深度：WeKnora 是完整平台 UI；knowmate 是轻量 Vue 测试工作台，视觉和流程已接近，但信息密度、设置项、命令面板、组织空间和 Chat 输入区能力不足。

v0.7 已按“可用知识库平台 Lite”的 P0 范围完成，不直接追完整 Agent/Wiki/RBAC 大范围。v0.71 详见 `docs/weknora-local-comparison-v0.71-roadmap.zh-CN.md`，P0 已完成上传队列、文档下载/取消/移动、停止生成/自动标题/last-request state、retrieval trace 阶段化、真实 parser/storage/system status 和 Command Palette；附件上下文、FAQ import progress、per-user pin/favorites 预留进入 P1/P2，RBAC-lite 单独延后规划。

## 源码依据

knowmate 当前主要依据：

- API 汇总：`app/api/v1/router.py`
- 数据模型：`app/db/models.py`
- RAG：`app/rag/parser.py`、`app/rag/chunker.py`、`app/rag/retriever/__init__.py`
- 服务：`app/services/*`
- 前端路由：`frontend/src/router/index.ts`
- 前端页面：`frontend/src/views/*`
- 当前版本说明：`README.md`、`CHANGELOG.md`

WeKnora 当前主要依据：

- API 注册：`internal/router/router.go`
- API 注解清单：`internal/handler/*.go`
- 知识库类型与配置：`internal/types/knowledgebase.go`、`internal/types/indexing_strategy.go`
- Chat/Session/Message：`internal/types/session.go`、`internal/types/message.go`
- Chat pipeline：`internal/application/service/chat_pipeline/*`
- Retriever factory：`internal/application/service/retriever/*`
- Parser engine registry：`internal/infrastructure/docparser/engine_registry.go`
- 前端路由与页面：`frontend/src/router/index.ts`、`frontend/src/views/*`
- API 文档索引：`docs/api/README.md`

## 复刻程度总览

| 模块 | knowmate 状态 | WeKnora 状态 | 复刻判断 | v0.7 建议 |
| --- | --- | --- | --- | --- |
| 模型配置 | OpenAI-compatible 模型 CRUD、凭据加密、KnowledgeQA/Embedding/Rerank 类型边界 | 模型 CRUD、provider 列表、Ollama、WeKnoraCloud、VLM/ASR/rerank check | 部分复刻 | 补 provider preset、模型类型 UI 分组、rerank 绑定 |
| 知识库 | document/faq、模型绑定、切分、parser rules、indexing strategy、vector store、capabilities、pin、KB detail settings | document/faq/wiki、共享、pin、复制、移动、capabilities、KB 编辑器多 tab | 部分复刻 | v0.7 已补 KB 编辑器增强、pin、capabilities；复制/移动延后 |
| 文档 | 上传、手动文本、URL、删除、重处理、预览、chunk | 上传文件/文件夹、URL、手动、下载、预览、取消解析、移动、处理 spans、图片信息 | 部分复刻 | 做处理 timeline、取消解析、下载、移动/复制、上传进度 |
| FAQ | CRUD、CSV/XLSX 导入导出、搜索测试、标签、相似问法、FAQ 索引模式 | FAQ CRUD、批量 upsert、导出、search、相似问法、字段批量更新、导入进度/last result | 部分复刻 | v0.7 已补相似问法和 FAQ 索引模式；导入进度/历史结果延后 |
| Chunk | list chunks、preview、parent-child metadata | chunk CRUD、按 id 查、删除 generated question、图片信息、问题生成 | 部分复刻 | 做 chunk 编辑/禁用、generated questions 管理 |
| 检索 | Qdrant vector、PostgreSQL FTS、RRF hybrid、parent-child、rerank 边界 | composite retrieve、多后端、BM25/sparse、fan-out、rerank、web search、wiki boost、graph | 部分复刻 | 补检索 trace UI、rerank 模型绑定、真实 sparse 后端预留 |
| Quick Q&A | 单/多 KB scope、文件范围检索、Chat mention、SSE、query rewrite、sources/trace | 多 KB/文件 mention、knowledge-qa、agent-qa、continue stream、stop、title、Web/IM | 部分复刻 | v0.7 已补 mention scope；停止生成、自动标题、附件边界延后 |
| Parser | builtin txt/md/pdf/docx/csv/json/xlsx、ocr 占位 | DocReader、simple、WeKnoraCloud、MinerU、MinerU Cloud、图片/音频、远程 engine 合并 | 部分复刻 | 做 parser 状态 API 和 KB parser tab，OCR/MinerU 仍可占位 |
| 存储 | local upload、storage provider 占位 | local/MinIO/COS/TOS/S3/OSS/KS3/OBS、预签名文件、存储状态检查 | 小部分复刻 | 做 local 文件下载/预览闭环，对象存储继续延后 |
| 前端导航 | Chat、知识库、设置中心 | 平台 shell、知识库、Agent、Chat、组织、设置、命令面板、用户菜单 | 部分复刻 | 做命令面板、KB detail 一体化页面、Chat 输入区增强 |
| 账号/RBAC | 单租户默认 `10000`，无登录 | auth、tenant、member、invitation、RBAC、audit、system admin | 未复刻 | v0.7 可做极简登录/RBAC-lite，完整延后 |
| Agent/MCP/Skills | 无 | agents、agent stream、tool approvals、MCP services、skills | 未复刻 | v0.8+ |
| Wiki/Graph | strategy flag 占位 | wiki pages、graph、lint、issues、auto-fix、wiki tools | 未复刻 | v0.8+，v0.7 只保留配置入口 |
| 外部数据源/IM/Web Search | 轻量 URL 导入 | datasource、IM channels、web-search providers、web fetch/search | 未复刻 | v0.8+；v0.7 可只做 Web Search 设置占位 |
| 评估 | 无 | evaluation API、dataset/metrics | 未复刻 | v0.8+ |

## 后端核心能力对比

### 1. API 面

knowmate 已有 API：

- `/api/v1/models`
- `/api/v1/model-config`
- `/api/v1/knowledge-bases`
- `/api/v1/knowledge-bases/{kb_id}/documents`
- `/api/v1/knowledge-bases/{kb_id}/faqs`
- `/api/v1/knowledge-bases/{kb_id}/tags`
- `/api/v1/documents`
- `/api/v1/chunker/preview`
- `/api/v1/parser-engines`
- `/api/v1/knowledge-search`
- `/api/v1/quick-answer`
- `/api/v1/quick-answer/stream`
- `/api/v1/chat-sessions`
- `/api/v1/retrieval-config`
- `/api/v1/vector-stores`
- `/api/v1/tasks`

WeKnora 本地源码里还包括大量未复刻 API：

- Auth：`/auth/login`、`/auth/register`、`/auth/refresh`、`/auth/me`、OIDC、auto setup。
- Tenant/RBAC：`/tenants`、members、invitations、audit-log、system admin。
- Organization：`/organizations`、共享知识库/Agent、加入申请。
- Knowledge advanced：copy、move、pin、download、cancel-parse、spans、batch、image update。其中 pin 和 processing spans 已在 knowmate v0.7 P0 落地，copy/move/download/cancel-parse/image update 仍未复刻。
- FAQ advanced：similar questions、fields batch update、import progress、last result display。
- Session/Chat advanced：`knowledge-qa`、`agent-qa`、stop、continue stream、title、batch delete、message search。
- Agent/MCP/Skills：`/agents`、`/mcp-services`、`/skills`、tool approvals。
- Wiki：`/knowledgebase/{kb_id}/wiki/*`。
- System：parser engine check、storage engine check/status、docreader reconnect。
- Web Search：providers CRUD/test。
- DataSource：source CRUD/sync/logs/resources。
- Evaluation：评估任务。

v0.7 取舍：

- 应补：knowledge advanced、FAQ advanced、session/chat advanced 的非 Agent 部分。
- 可补最小版：auth/tenant/RBAC-lite，只为后续多 workspace 打基础。
- 暂缓：Agent/MCP/Wiki/DataSource/IM/Evaluation 全量。

### 2. 数据模型

knowmate 已有表：

- `tenants`
- `knowledge_bases`
- `knowledge_tags`
- `model_configs`
- `vector_stores`
- `chat_sessions`
- `chat_messages`
- `knowledges`
- `processing_tasks`
- `faq_entries`
- `chunks`

WeKnora 对应和扩展：

- 核心同名概念：`tenants`、`models`、`knowledge_bases`、`knowledges`、`sessions`、`messages`、`chunks`。
- 已扩展概念：users/auth tokens、tenant members、tenant invitations、audit logs、organizations、shares、agents、mcp services、datasources、wiki pages/issues/logs、task pending/dead letters、user favorites、web search providers、vector stores。

knowmate 的缺口不是核心表完全缺失，而是缺少平台级 ownership 和操作历史：

- KB 没有 `creator_id`，难以复刻 WeKnora “Contributor 可管理自己创建的 KB，Admin/Owner 可管理全局”的 RBAC 规则。
- Session 没有 `user_id`、`last_request_state`、source/channel，难以复刻 Web/IM/Agent 输入状态恢复。
- Message 没有 mentioned items、images、attachments、agent steps、rendered content、channel。
- Knowledge 没有 processing spans/timeline、download/presigned file 概念、move/copy 任务。
- FAQ 缺少 similar questions 和 index mode。

v0.7 取舍：

- v0.7 已补：KB pin、message mentioned_items、knowledge processing spans。
- 后续应补：`creator_id`、session last request state、attachments 边界和更完整用户/权限字段。
- 可补：user/auth 最小表。
- 暂缓：organization shares、agent shares、wiki tables。

### 3. RAG 主链路

knowmate 当前链路：

```text
KB -> document upload/manual/url
  -> parser registry
  -> adaptive chunking
  -> parent/child chunks
  -> PostgreSQL chunk metadata/search_text
  -> Qdrant payload/vector
  -> vector/keyword/hybrid retrieval
  -> optional rerank
  -> answer prompt
  -> LLM answer + sources + retrieval trace
  -> chat session/message persistence
```

WeKnora 更完整链路：

```text
KB capabilities/indexing strategy
  -> parser engine resolution (simple/docreader/weknoracloud/mineru)
  -> storage provider file service
  -> processing spans / task queue / post-process
  -> chunking + image/audio/multimodal metadata
  -> vector/sparse/wiki/graph indexing
  -> composite retriever by KB vector store binding or tenant engines
  -> query understanding / expansion / entity extraction
  -> parallel search / FAQ merge / rerank / history merge / web fetch
  -> prompt templates / context template
  -> knowledge-qa or agent-qa stream
  -> message references, agent steps, tool results
```

核心差距：

- knowmate 目前 retrieval pipeline 是可用但线性；WeKnora 是插件/事件式 chat pipeline。
- knowmate query rewrite 只有追问改写；WeKnora 有 query understand、expansion、entity extraction、FAQ merge、history merge、web fetch 等模块。
- knowmate sources 足够展示答案来源；WeKnora 的 message references、rendered content、agent steps 更利于历史重建。
- knowmate parser/chunker 方向正确，但缺 DocReader/MinerU/图片/音频/公式/远程图片处理。

v0.7 建议只补“Quick Q&A 质量可见性”，不要改成完整 pipeline 框架：

- 增强 retrieval trace：展示 vector/keyword/rerank/parent expansion 各阶段命中数、阈值、耗时。
- 保存 rendered context 或 prompt context 摘要，便于用户解释回答。
- 增加 stop generation、session title 生成。
- 增加 mention scopes，让单次提问可选多个 KB 或限定文件。

## 前端效果与工作流对比

### 1. 信息架构

knowmate：

- `/#/chat`
- `/#/knowledge-bases`
- `/#/knowledge-bases/:kbId/documents`
- `/#/knowledge-bases/:kbId/faqs`
- `/#/settings`

WeKnora：

- `/login`、`/register`、`/join`
- `/platform/knowledge-bases`
- `/platform/knowledge-bases/:kbId`
- `/platform/agents`
- `/platform/creatChat`
- `/platform/knowledge-bases/:kbId/creatChat`
- `/platform/chat/:chatid`
- `/platform/organizations`
- `/platform/settings`
- 全局命令面板、用户菜单、租户/空间入口。

差距：

- knowmate 把 KB list、document view、FAQ view 拆成多个轻量页面；WeKnora 是 KB detail 一体化页面，内部有文档/FAQ/Wiki/设置/共享等模块。
- knowmate 设置中心是外壳；WeKnora 设置中心包含模型、Ollama、parser、storage、retrieval、MCP、Web Search、Tenant、System、API info、Chat history 等。
- knowmate 没有命令面板和平台级搜索。

v0.7 建议：

- 把 KB detail 做成 WeKnora-like 一体化页面：概览、文档/FAQ、设置、解析/切分、索引策略、任务。
- 增加 Command Palette 最小版：搜索 KB、文档、FAQ、会话，支持跳转。
- 设置中心增加真实 parser engine API 和 storage status API，而不是静态占位。

### 2. Chat 页面

knowmate 已有：

- 会话列表、搜索、pin、批量删除。
- SSE 流式回答。
- 每条 assistant message 的 sources 和 retrieval trace。
- query rewrite 开关。
- 推荐问题。
- Markdown 渲染。

WeKnora 更多：

- 输入框 Agent/普通模式切换。
- 知识库/文件 mention 选择器。
- 图片和文件附件。
- Web Search、MCP 工具、Agent 工具调用、tool approval。
- 停止生成、继续流、自动标题。
- 工具结果渲染：搜索结果、chunk detail、document info、graph query、wiki edit、database query、plan/thinking。
- Chat input 恢复上次选择状态。

v0.7 建议：

- P0：Chat 输入框支持 `@知识库`、`@文件` 范围选择；后端 quick-answer/search 支持多 KB 或 KB+knowledge_ids scope。状态：v0.7 已完成。
- P0：支持停止生成；服务端在 stream 中有可取消边界。
- P1：自动生成会话标题，失败时回退首句。
- P1：附件边界：先支持 txt/md/pdf/docx 上传为临时上下文，不写知识库或写临时 KB 二选一。
- P2：Mermaid 渲染和更完整 Markdown 安全清洗。

### 3. 知识库页面

knowmate 已有：

- KB 创建/编辑基础信息。
- document/faq 类型。
- 模型绑定。
- VectorStore 选择。
- indexing strategy。
- 标签、文档、FAQ、任务状态。

WeKnora 更多：

- KB 卡片区分 Mine/Shared/All。
- KB pin。
- KB 复制、移动。
- KB 共享到组织。
- KB detail 内部设置：模型、parser、chunking debug、indexing、vector store、storage、graph、share、advanced。
- Wiki Browser。
- DataSource settings。

v0.7 建议：

- P0：KB 编辑器补齐创建后可修改模型/切分/parser/indexing/vector store 的 WeKnora-like 设置面板，并明确修改后需要重建索引。
- P0：KB pin 和列表排序。状态：v0.7 已完成。
- P1：KB 复制/重建任务，文档 move 到其他 KB。
- P1：KB capabilities 字段，前端用它启停能力入口。
- P2：共享入口先不做，除非 v0.7 确认要做 RBAC-lite。

### 4. 文档页面

knowmate 已有：

- 文档列表、筛选、标签、上传、手动文本、URL 导入。
- 批量删除/重处理。
- 文档预览、chunk outline。
- task status 和失败原因。

WeKnora 更多：

- 上传文件夹。
- 动态上传进度。
- 下载原文件。
- 取消解析。
- 处理 stages/spans/timeline。
- 文件移动。
- 图片信息更新。
- 更完整的文档预览和 storage/presigned 文件访问。

v0.7 建议：

- P0：文档处理 timeline/spans，至少记录 parse、chunk、embed、upsert、postprocess 阶段和耗时/错误。
- P0：上传队列和多文件进度。
- P1：下载原文件、取消解析、失败任务重试更细化。
- P1：文档移动到其他 KB。
- P2：文件夹上传。

### 5. FAQ 页面

knowmate 已有：

- FAQ CRUD。
- CSV/XLSX 导入导出。
- 搜索测试。
- 标签筛选/批量分配。

WeKnora 更多：

- similar questions。
- FAQ index mode：question_only / question_answer。
- question index mode：combined / separate。
- fields batch update。
- import progress 和 last result display status。

v0.7 建议：

- P0：FAQ similar questions 数据模型和 UI。
- P0：FAQ 索引模式配置，并影响写入 chunks/Qdrant 的内容。
- P1：FAQ 字段批量更新。
- P1：导入进度和 last import result 持久展示。

## v0.7 推荐任务包

### P0：Quick Q&A 平台化补齐（v0.7 已完成）

目标：让现有主线更像 WeKnora 的可用产品，而不是测试台。

1. KB 详情一体化页面
   - 概览、文档/FAQ、设置、解析/切分、索引策略、任务。
   - 创建后可编辑模型、parser、chunking、indexing。
   - 改配置后提示需要重处理/重建。
   - 状态：已完成，见 TASK-012 / TASK-013。

2. Chat mention scope
   - 输入框支持选择知识库和文件。
   - 后端 search/quick-answer 支持 `knowledge_base_ids` 和 `knowledge_ids`。
   - sources 标记来自哪个 KB/文档。
   - 状态：已完成，见 TASK-014 / TASK-015。

3. 文档处理 timeline
   - 新增 processing spans。
   - worker 按 parse/chunk/embed/upsert/finalize 写阶段状态、耗时和错误。
   - 前端文档页展示时间线。
   - 状态：已完成，见 TASK-016 / TASK-017。

4. FAQ similar questions + index mode
   - FAQ entry 支持相似问法。
   - KB FAQ config 支持 question_only/question_answer、combined/separate。
   - 重建索引时按配置生成 chunk/embedding payload。
   - 状态：已完成，见 TASK-018 / TASK-019。

5. KB pin + capabilities
   - 用户未实现前可按默认 tenant 级别存储。
   - capabilities 从 kb_type/indexing_strategy 计算，供前端启停入口。
   - 状态：已完成，见 TASK-010 / TASK-011。

### P1：体验与可观测性增强

1. 上传队列和多文件进度。
2. 停止生成、会话自动标题。
3. 文档下载、取消解析、移动到其他 KB。
4. Retrieval trace 增强：vector/keyword/rerank/parent expansion 阶段拆开显示。
5. Command Palette 最小版：搜索 KB、文档、FAQ、会话。
6. 设置中心接入真实 parser engine status 和 storage status API。

### P2：为后续平台能力铺路

1. Auth/RBAC-lite
   - user、password hash、session/JWT、tenant member。
   - 默认 owner/admin/contributor/viewer 角色。
   - 保持 `DEFAULT_TENANT_ID=10000` 迁移兼容。

2. 附件上下文
   - 先支持文本型附件抽取后进入本轮 prompt。
   - 暂不做长期知识库入库，避免和文档上传重复。

3. 文件夹上传。
4. Web Search provider 设置占位和 API 形状。
5. Mermaid 渲染和更完整 Markdown 安全渲染。

## 不建议放入 v0.7 的范围

以下能力在 WeKnora 中很重要，但会显著扩大 v0.7 面积，不建议和 Quick Q&A 平台化补齐混在一个版本：

- Agent Mode 全量。
- MCP service/tool approval。
- Wiki Mode、wiki graph、wiki auto-fix。
- 知识图谱抽取和 Neo4j/graph retrieval。
- IM 渠道。
- 外部数据源同步。
- WeKnoraCloud、MinerU Cloud、完整 OCR/VLM/ASR。
- 多组织共享和完整 RBAC。
- Evaluation/dataset/metrics。
- 多 vector backend 全量，例如 OpenSearch、Elasticsearch、Milvus、Doris、Weaviate、Tencent VectorDB。

## 建议的 v0.7 验收标准

1. 用户能在一个 KB detail 页面完成创建后的模型、切分、parser、索引策略调整，并触发重建。
2. 用户能在 Chat 中选择多个知识库或限定文件提问，回答 sources 明确显示来源。
3. 用户能看到每个文档从解析到向量入库的阶段状态和失败原因。
4. FAQ 支持相似问法和索引模式，搜索测试能体现差异。
5. KB 列表支持 pin，常用知识库稳定置顶。
6. 检索 trace 能解释 vector、keyword、rerank、parent-child 的每一步。
7. 前端所有新增错误均为中文可读文案，不渲染原始对象。
8. API key 和敏感配置继续只显示配置状态和尾号。

## 推荐拆分顺序

1. 数据模型和迁移：processing spans、FAQ similar questions/config、KB pin/capabilities、message scope。
2. 后端 service/API：KB setting update、multi-scope search、FAQ rebuild、spans 写入。
3. 前端 KB detail 重组：先不改视觉大框架，逐步收敛页面。
4. Chat 输入区增强：mention scope、stop generation、title。
5. 文档页增强：timeline、上传队列、下载/取消/移动。
6. trace 和设置中心增强。

这个顺序能最大限度复用现有 Quick Q&A 主链路，并避免 v0.7 被 Agent/Wiki/RBAC 大范围打散。
