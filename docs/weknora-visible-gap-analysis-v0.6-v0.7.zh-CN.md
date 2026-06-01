# knowmate 与 Tencent/WeKnora 可见功能差距分析

日期：2026-05-30

范围：本报告是非点击版差距分析，初版依据 Tencent/WeKnora 公开 README、CHANGELOG、DeepWiki 源码索引，以及本地 knowmate v0.5 的 README、CHANGELOG 和前端路由/页面结构整理；2026-05-31 已按 knowmate v0.61 更新当前基线；2026-06-01 已补充 knowmate v0.7 P0 完成状态。由于 Chrome 插件安全策略阻止对 WeKnora 线上生产域名进行自动化点击，本报告不包含线上页面真实点击验证结果。

主要参考来源：

- Tencent/WeKnora GitHub：https://github.com/Tencent/WeKnora
- Tencent/WeKnora README 功能概览：https://github.com/Tencent/WeKnora
- Tencent/WeKnora CHANGELOG：https://raw.githubusercontent.com/Tencent/WeKnora/main/CHANGELOG.md
- DeepWiki 前端、导航、知识库、聊天、设置页索引：
  - https://deepwiki.com/Tencent/WeKnora/7.1-navigation-and-menu-system
  - https://deepwiki.com/Tencent/WeKnora/7.2-knowledge-base-interface
  - https://deepwiki.com/Tencent/WeKnora/7.3-chat-interface-and-agent-display
  - https://deepwiki.com/Tencent/WeKnora/7.4-settings-and-configuration-interface

## 一句话结论

knowmate v0.7 已经把 Quick Q&A 的核心 RAG 主链路、会话化问答、标签、文档预览、FAQ 导入导出、批处理反馈、设置中心外壳、KB capabilities / pin、KB 详情一体化设置、多 scope 检索、Chat mention、文档处理 timeline、FAQ 相似问法和 FAQ 索引模式搭起来了，当前最大的差距不再是“能不能上传文档并问答”，而是 WeKnora 更完整的 Agent、Wiki、工作区/RBAC、高级解析、外部导入、多端入口和企业级可观测性。

## v0.7 更新说明

截至 2026-06-01，TASK-010 到 TASK-019 已作为 knowmate `v0.7` 归档完成。v0.7 仍未进入 Agent/Wiki/RBAC 大范围，而是完成原 v0.7 P0 的 Quick Q&A 平台化补齐：

- KB capabilities 与 pin。
- KB 详情一体化页面和创建后设置编辑。
- 多知识库 / 文件范围检索和 Chat mention scope。
- 文档处理 parse/chunk/embed/upsert/finalize timeline。
- FAQ 相似问法、FAQ 索引模式和命中问法展示。

因此，本文中原建议放到 v0.7 P0 的项目已经落地。上传队列、停止生成、自动标题、文档下载/取消/移动、retrieval trace 细化、Command Palette、真实 parser/storage status、附件上下文和 RBAC-lite 进入 v0.71 或后续候选。

## v0.61 更新说明

截至 2026-05-31，TASK-001 到 TASK-009 已作为 knowmate `v0.61` 归档完成。v0.61 没有进入 Agent/Wiki/RBAC 大范围，而是集中补齐 v0.6 之后最靠近 WeKnora Quick Q&A 产品体验的知识管理和会话体验：

- 标签/分类：已实现知识库级标签、文档/FAQ 标签筛选和批量分配，`tag_id` 写入 PostgreSQL 和 Qdrant payload。
- 文档预览：已实现文档预览 API、摘要/正文预览、chunk outline 和前端预览抽屉。
- FAQ 导入导出/搜索测试：已实现 CSV/XLSX append/replace 导入、导入失败摘要、CSV/XLSX 导出和 FAQ 检索测试抽屉。
- 批处理体验：已实现批量删除/重处理的 requested/succeeded/failed/failures 摘要、任务 `batch_summary` 和失败任务重试入口。
- 设置中心：已实现 `/#/settings` WeKnora-like 设置中心外壳，整合模型、VectorStore、检索、解析器和存储状态；高级 parser/storage provider 仍为禁用占位。
- 会话体验：已实现会话搜索、批量删除和基于 FAQ/chunk generated_questions 的推荐问题入口。

因此，本文中原建议放到 v0.7 的“标签/分类、文档预览、FAQ 导入导出/搜索测试、批处理反馈、设置中心整合、会话搜索/批量删除/推荐问题”已经前移并落地为 v0.61。仍未完成的主要差距是 RBAC-lite/workspace、Agent Mode、Wiki Mode、高级解析/OCR/MinerU、对象存储真实 provider、外部数据源同步和更完整的系统可观测性。

建议 v0.6 不要直接追完整 WeKnora v0.6 的企业级 RBAC/MCP/CLI 范围，而是优先把现有 Quick Q&A 做成真正可用的聊天产品：

- 多轮会话
- 流式回答
- 会话列表
- query rewrite
- 每轮 sources 和检索 trace
- 会话级参数设置

v0.7 再补知识管理体验和 workspace-lite：

- 标签/分类
- 文档预览
- FAQ 导入导出
- 上传/批处理结果反馈
- RBAC-lite
- 设置中心整合

Agent Mode、Wiki Mode、MCP、IM、小程序、Chrome Extension、复杂外部数据源同步建议放到 v0.8 以后。

## knowmate v0.61 当前基线

当前可见页面：

- `/#/chat`：会话化 Quick Q&A、流式回答、来源/trace 展示和知识搜索调试。
- `/#/knowledge-bases`：知识库列表、创建、删除、类型选择、模型绑定、VectorStore 选择、索引策略。
- `/#/knowledge-bases/:kbId/documents`：文档管理、标签筛选、上传/导入、批量操作、处理进度、预览抽屉和 chunk 查看。
- `/#/knowledge-bases/:kbId/faqs`：FAQ 管理、标签筛选、CSV/XLSX 导入导出和 FAQ 检索测试。
- `/#/settings`：设置中心，组织模型配置、Qdrant VectorStore、检索/切分配置、解析器状态和存储状态。

已完成的可见能力：

- 文档知识库和 FAQ 知识库。
- 知识库绑定 QA 模型和 Embedding 模型。
- 知识库级 indexing strategy：vector、keyword、parent-child、rerank；Wiki/KG 目前作为不可用边界展示。
- 上传、重处理、重建任务记录。
- 文档上传、手写文本/Markdown 导入、轻量 URL 导入。
- 知识库级标签、文档/FAQ 标签筛选和批量分配。
- 文档状态、chunk 数、任务状态、失败原因、批量删除、批量重处理、批处理部分失败摘要。
- 文档预览抽屉，展示摘要、正文预览、chunk outline 和 chunk 内容。
- FAQ CSV/XLSX append/replace 导入、导出和检索测试。
- Qdrant 向量索引和 VectorStore 管理。
- vector + keyword + RRF hybrid retrieval。
- 可选 rerank 边界。
- sources 展示分数、chunk、metadata 等检索解释字段。
- 会话列表、多轮消息、SSE 流式 quick-answer。
- 会话搜索、批量删除、pin/unpin 和推荐问题。
- 每条 assistant 消息保存 sources、retrieval trace 和非敏感 model config。
- 可选 query rewrite，展示 original query / rewritten query / rewrite 状态。
- 模型 API Key 加密保存，前端只显示配置状态和尾号。

明确未实现的能力：

- 登录、用户、RBAC、多租户隔离。
- OCR、MinerU、图片类文件解析、VLM。
- 真正 BM25 或外部 sparse search 引擎。
- GraphRAG、多维索引、Agent Mode、Wiki Mode。
- WeKnoraCloud、Ollama 拉取、ASR。
- Agent Mode、Wiki Mode、MCP 工具、IM 渠道、小程序、复杂外部数据源同步。
- 真实对象存储 provider 和高级 OCR/MinerU provider 接入。

## 可见功能差距矩阵

### 1. 导航和工作区外壳

WeKnora 已有的可见能力：

- 左侧主导航包含知识库、Agent、组织/工作区、创建会话、设置等入口。
- Chat 入口下有按时间分组的会话列表。
- 支持 Ctrl/Command+K 全局命令面板。
- 多租户用户可见 tenant/workspace 切换器。
- 登录、初始化、租户状态相关路由守卫。

knowmate v0.61 状态：

- 侧边栏包含 Chat、知识库和设置中心。
- Chat 已有会话列表、搜索、pin/unpin 和批量删除。
- 没有命令面板、tenant 切换、组织入口、Agent 入口。
- 没有登录态和初始化路由守卫。

差距判断：

- 已完成：Chat 会话导航和设置入口分组。
- 中优先级：命令面板。
- 后续再做：组织入口和 tenant 切换，需要等登录/RBAC 基础存在后再补。

### 2. Chat / Quick Q&A 体验

WeKnora 已有的可见能力：

- 多轮聊天会话。
- SSE 流式响应。
- 会话列表按时间分组。
- 会话 pin/unpin、搜索、批量删除。
- QA 模式和 Agent 模式区分。
- 输入框可选择/提及知识库或文件。
- 新会话推荐问题。
- 图片等消息附件。
- Markdown、代码高亮、Mermaid、安全 HTML 清洗。
- 历史消息可重建 Agent 思考步骤。

knowmate v0.61 状态：

- 会话化 Quick Q&A 工作台。
- 左侧会话列表，支持创建、选择、搜索、重命名、删除、批量删除和 pin/unpin。
- 新增 quick-answer SSE 流式接口和前端流式渲染。
- knowledge-search 作为折叠调试入口保留。
- 回答支持 Markdown 渲染。
- sources 使用 SourceCard 展示。
- 每条 assistant 消息保存并展示 sources / retrieval trace。
- 支持追问 query rewrite，trace 中展示 original query / rewritten query。
- 新会话空态展示来自 FAQ 和 chunk generated_questions 的推荐问题。
- 没有附件、提及选择器、Mermaid 渲染。

v0.6/v0.61 已补齐：

- 新增 `chat_sessions`。
- 新增 `chat_messages`。
- 新增会话侧边栏/会话列表。
- 新增 quick-answer SSE 流式接口。
- 每条 assistant 消息保存 answer、sources、retrieval trace。
- 支持追问场景的 query rewrite。
- 支持会话搜索、批量删除和推荐问题。

v0.61 后继续补：

- 知识库/文件提及选择器。
- Mermaid 渲染。

更后续：

- Agent 步骤重建和工具调用可视化，等 Agent Mode 实现后再做。

### 3. 知识库列表和创建/编辑

WeKnora 已有的可见能力：

- 文档、FAQ、Wiki 等知识库类型。
- 知识库编辑弹窗包含基础信息、索引策略、模型配置、切分配置、知识图谱配置。
- 知识库可绑定 LLM、Embedding、Rerank、VLM。
- 可选择 vector/wiki 索引方式。
- newer UI 中有 Mine、Shared、All 等组织空间视图。
- 有用户级 KB pinning 和共享/组织能力。

knowmate v0.61 状态：

- 知识库列表、创建、删除。
- 支持 document / faq 两类。
- 绑定 QA 和 Embedding 模型。
- rerank 有配置边界，但不是完整 per-KB rerank 模型工作流。
- 创建时可设置索引策略和切分配置。
- 没有 Wiki 知识库、VLM 绑定、图谱设置、用户 pin、共享空间。

差距建议：

- v0.6：把知识库创建表单升级为真正的“创建/编辑配置”弹窗，创建后也能修改模型、切分、索引策略。
- v0.7：增加标签/分类和 pin。
- 后续：Wiki 类型和 GraphRAG 设置。

### 4. 文档管理

WeKnora 已有的可见能力：

- 上传文件、上传文件夹、URL 导入、手动创建。
- 支持 PDF、Word、TXT、Markdown、HTML、图片、CSV、Excel、PPT、JSON。
- 图片类文件依赖 VLM，复杂解析可走 OCR/MinerU。
- 文档卡片/列表展示处理状态、摘要、chunk 数、标签/分类。
- 支持 PDF、Docx、Excel、Markdown 等文档预览。
- 可以按 chunk offset 还原全文结构。
- 批量上传有进度和部分失败摘要。
- 动态分页和无限滚动。

knowmate v0.61 状态：

- 文件上传、手写文本/Markdown 导入、轻量 URL 导入。
- 支持 txt、md、pdf、docx、csv、json、xlsx。
- 没有文件夹上传。
- 没有图片、PPT、HTML 一等格式、OCR、MinerU、VLM。
- 文档列表有状态、筛选、chunk 数、task 状态、错误信息。
- 有文档预览抽屉，展示摘要、正文预览、chunk outline 和 chunk 内容。
- 批量删除/重处理已支持，并返回 requested/succeeded/failed/failures 摘要；上传进度仍较弱。

差距建议：

- 已完成：文档预览、更清楚的处理结果展示、标签/分类。
- 后续：文件夹上传、批量上传进度。
- 后续：图片/OCR/MinerU/PPT/高级 HTML 抽取和全文重建。

### 5. FAQ 管理

WeKnora 已有的可见能力：

- FAQ 条目卡片。
- 创建 FAQ、导入 FAQ、搜索测试、导出 FAQ、批量操作。
- FAQ 批量导入带进度。
- 导入完成后展示总数、成功数、失败数、跳过数、导入模式、失败条目下载地址、导入时间。
- FAQ 条目也支持标签/分类。

knowmate v0.61 状态：

- 有 FAQ 知识库类型和 FAQ CRUD。
- FAQ 会写入 chunks 和 Qdrant，复用 quick-answer/knowledge-search。
- 有 FAQ 管理页。
- 已有 FAQ CSV/XLSX 导入导出、导入失败摘要和 FAQ 检索测试。
- 已有 FAQ 标签筛选和批量分配。

差距建议：

- 已完成：FAQ 导入、导出、搜索测试面板、标签和基础批量操作。
- 后续：更接近 WeKnora 的持久导入任务历史、失败条目下载地址和更细粒度批量操作。

### 6. 检索和搜索调试

WeKnora 已有的可见能力：

- Dense retrieval、BM25/sparse retrieval、GraphRAG、parent-child chunking、多维索引。
- Hybrid retrieval 优化。
- 每个来源可有 parser/storage engine 配置。
- E2E 测试和全链路可视化，包含召回命中率、BLEU/ROUGE 等评估。

knowmate v0.61 状态：

- Qdrant dense retrieval。
- 应用层 jieba + PostgreSQL FTS keyword retrieval。
- RRF hybrid。
- 可选 rerank。
- parent-child context expansion。
- knowledge-search 调试 API 和 UI。
- per-KB indexing strategy 会约束 vector/keyword/parent-child/rerank。
- 没有真正 BM25、GraphRAG、多维索引、E2E 评估面板、召回指标。

差距建议：

- v0.6：query rewrite + 每轮检索 trace。
- v0.7：增强搜索评估/调试页面，支持保存测试问题和命中结果。
- 后续：真正 BM25/Elasticsearch/OpenSearch/ParadeDB、GraphRAG、评估指标。

### 7. Agent Mode 和工具调用

WeKnora 已有的可见能力：

- Agent 列表和自定义 Agent。
- ReAct 多步推理。
- 内置工具、MCP 工具、Web Search。
- Agent 流式过程展示：思考卡片、工具调用卡片、工具结果渲染、人工审批卡片、计划状态可视化。
- Agent 设置：最大迭代次数、temperature、system prompt、动态占位符。
- Data Analyst agent、Agent skills、沙箱执行等扩展能力。

knowmate v0.61 状态：

- 没有 Agent 页面。
- 没有 agent 数据模型。
- 没有工具调用、MCP、Web Search、Agent stream UI。
- Chat 只做 Quick Q&A。

差距建议：

- 不建议 v0.6 做，除非多轮会话和流式回答已经完成。
- v0.8 可做 Agent Mode MVP：只读知识库检索 + 可选 web search + 工具调用展示。

### 8. Wiki Mode 和知识图谱

WeKnora 已有的可见能力：

- Wiki Mode GA：由 Agent 从文档自动生成结构化、互链 Markdown Wiki。
- Wiki 浏览器。
- 可视化知识图谱。
- 大规模 Wiki ingest 使用任务队列和 DLQ。
- 图谱设置包含实体抽取和关系映射。

knowmate v0.61 状态：

- `enable_wiki` 和 `enable_knowledge_graph` 只是保存/展示为不可用边界。
- 没有 wiki page 数据模型。
- 没有 Wiki 浏览器。
- 没有图谱可视化、图数据库、图谱抽取、图检索。

差距建议：

- 不做 v0.6。
- v0.8 或 v0.9 可做 Wiki MVP。
- 第一阶段建议先做“从 KB chunks 生成只读 Wiki 页面”，不要一开始就做完整图谱。

### 9. 设置中心

WeKnora 已有的可见能力：

- 全屏设置弹窗或 `/platform/settings` 设置路由。
- 设置分区：通用、模型、Agent、Ollama、解析器、存储、系统信息。
- 模型按 chat、embedding、rerank、VLLM 分类。
- 内置模型有标记，并禁用编辑/删除。
- 模型编辑器支持本地 Ollama 和远程模型。
- Parser 设置包含 builtin/simple/MinerU 和远程 docreader 发现。
- Storage 设置包含 local、MinIO、COS、TOS 等对象存储。
- System Info 展示版本、edition、commit、build time、Go version、keyword/vector/graph 引擎、MinIO 状态、DB migration 版本。
- General 设置包含语言、主题、字体。

knowmate v0.61 状态：

- 模型、VectorStore、检索配置已收敛到 `/#/settings` 设置中心外壳。
- 模型供应商更少。
- Parser/storage 已有可见状态分区，高级 provider 仍为禁用占位。
- 没有 Ollama 页面、Agent 设置、系统信息页、语言/主题/字体偏好。

差距建议：

- 已完成：设置外壳、parser/storage 可见状态。
- 中优先级：系统信息页或状态卡片。
- 后续：Ollama、WeKnoraCloud、更多 provider 预设。

### 10. 模型供应商覆盖

WeKnora 已有的可见能力：

- Chat/LLM：OpenAI、Azure OpenAI、Anthropic、DeepSeek、Qwen、Zhipu、Hunyuan、Doubao、Gemini、MiniMax、NVIDIA、Novita AI、SiliconFlow、OpenRouter、Ollama。
- Embedding：Ollama、BGE、GTE、Zhipu、OpenAI-compatible。
- VLM 和 ASR 在设置/版本历史中出现。
- 多租户内置/托管模型共享。

knowmate v0.61 状态：

- Qwen/DashScope、DeepSeek、OpenAI-compatible chat/embedding/rerank。
- VLLM/ASR 是枚举占位。
- 没有 Ollama 拉取流程、VLM、ASR、内置模型共享。

差距建议：

- v0.6：把 OpenAI-compatible embedding 支持和 provider 预设做得更稳。
- v0.7：如果本地部署是重点，再补 Ollama 设置。
- 后续：VLM/ASR。

### 11. VectorStore、对象存储和数据源

WeKnora 已有的可见能力：

- Vector DB：PostgreSQL pgvector、Elasticsearch、Milvus、Weaviate、Qdrant、Apache Doris、Tencent VectorDB。
- 对象存储：Local、MinIO、S3、TOS、OSS、KS3、OBS。
- 数据源导入：飞书、Notion、语雀，支持同步。
- Chrome Extension 和 ClawHub Skill 作为导入入口。

knowmate v0.61 状态：

- Qdrant registry/factory 和 CRUD/test。
- 实际主要是本地文件存储。
- URL 导入是一次性轻量 HTML 抽取。
- 没有外部数据源同步或对象存储 provider UI。

差距建议：

- v0.6：继续只保 Qdrant，但加强 VectorStore 绑定校验和展示。
- v0.7：如果文件持久化要产品化，补 storage provider 设置。
- 后续：飞书/Notion/语雀同步和更多 VectorStore。

### 12. Auth、RBAC、组织和审计

WeKnora 已有的可见能力：

- Tenant RBAC：Owner、Admin、Contributor、Viewer。
- KB 资源 ownership。
- 租户级 audit log。
- 租户成员管理和多 workspace UX。
- 自助创建 workspace、邀请制 workspace。
- Viewer 或非创建者看不到/不能使用修改类按钮。
- OIDC 和 API Key auth 出现在版本历史中。

knowmate v0.61 状态：

- 单租户 `DEFAULT_TENANT_ID=10000`。
- 没有登录、用户、成员、角色、ownership、audit log、权限感知 UI。

差距建议：

- v0.6 不必须做，因为主线仍是 Quick Q&A。
- v0.7 建议做 RBAC-lite：
  - 登录/session。
  - 用户表。
  - workspace/tenant selector 外壳。
  - 先做 Owner/Admin/Viewer 三档。
  - KB ownership。
  - Viewer 隐藏/禁用写操作。
  - 对 KB、文档、模型等变更写 audit log。

### 13. 可观测性和系统运维

WeKnora 已有的可见能力：

- Langfuse 追踪 ReAct 循环、token 使用、工具调用和 pipeline trace。
- 系统信息页。
- Wiki ingest 任务队列和 DLQ。
- 版本升级时自动数据库迁移。

knowmate v0.61 状态：

- 有 processing_tasks 和状态。
- 没有 Langfuse/trace UI。
- 没有 token 使用展示。
- 没有系统信息页。
- 没有 DLQ。
- 没有自动迁移 UI。

差距建议：

- v0.6：把 retrieval trace 保存到 chat message，并在 source panel 可见。
- v0.7：补系统信息页和任务历史页。
- 后续：Langfuse 或 OpenTelemetry。

### 14. 外部客户端和多端入口

WeKnora 已有的可见能力：

- Web UI、REST API、CLI、Chrome Extension、WeChat Mini Program。
- IM 渠道：企业微信、飞书、Slack、Telegram、钉钉、Mattermost、微信。
- CLI 命令覆盖 auth、kb、doc、search、chat 等。

knowmate v0.61 状态：

- 只有 Web UI 和 REST API。
- 没有 CLI、浏览器插件、小程序、IM 集成。

差距建议：

- 不做 v0.6。
- API 稳定后可以先做 CLI，便于开发者和 Agent 使用。
- IM、移动端、浏览器插件应等 auth 和 source management 稳定后再做。

## v0.6 推荐范围

主题：会话化 Quick Q&A。

状态：已在 knowmate v0.6 主线中完成 P0，会话、流式回答、sources/trace、query rewrite 和基础会话操作已落地；System Info 页面未纳入本轮实现。

目标：把当前单轮 RAG 调试台升级为真正可持续使用的知识库聊天体验，同时不提前打开 Agent/Wiki/RBAC 的大范围。

建议交付：

1. Chat sessions
   - 新增 `chat_sessions` 表。
   - 新增 `chat_messages` 表。
   - 支持会话创建、列表、详情、重命名、删除。
   - 前端侧边栏展示按时间分组的会话列表。
   - 保存 user query、assistant answer、sources、retrieval mode、model IDs、时间戳。

2. 流式回答
   - 新增 quick-answer SSE endpoint。
   - 前端支持流式渲染。
   - 结束事件返回 sources 和 retrieval metadata。
   - 错误事件必须是中文可读消息。

3. 追问 query rewrite
   - session 有历史时可选执行 query rewrite。
   - debug metadata 展示 original query 和 rewritten query。
   - 模型配置缺失时不要静默 fallback。

4. 会话设置
   - 支持 mode、top_k、rerank、temperature、system prompt。
   - 可先做全局设置，后续再做 per-session。
   - 不向前端暴露原始内部配置对象。

5. Source 和 trace 体验
   - 每条 assistant message 绑定 source panel。
   - 展示 vector/keyword/RRF/rerank score、matched child、parent context、rewritten query、retrieval mode。

6. 基础会话操作
   - 重命名会话。
   - 删除会话。
   - 时间允许再做 pin/unpin。
   - 批量管理可以等会话列表稳定后再做。

7. 设置/系统状态小补强
   - 增加 System Info 页面或状态卡片。
   - 展示 app version、DB 状态、Qdrant 状态、Redis 状态、migration head、模型配置状态。

v0.6 建议排除：

- 完整 RBAC。
- Agent Mode。
- Wiki Mode。
- MCP 工具。
- IM 渠道。
- 多 VectorStore fan-out。
- 飞书/Notion/语雀同步。

## v0.7 推荐范围

主题：知识管理增强与 workspace-lite。

目标：补齐 WeKnora 可见知识管理体验，同时为后续 Agent/Wiki/多人协作铺最小地基。

建议交付：

1. 标签/分类
   - 文档和 FAQ 页面都有 tag sidebar。
   - 创建、重命名、删除标签。
   - 单条或批量分配标签。
   - 按标签筛选。

2. 文档预览
   - Markdown、TXT、CSV/Excel 基础表格、PDF 文本预览、DOCX 文本预览。
   - 尽量支持 chunk 到原文位置导航。
   - 展示 document summary。

3. FAQ 导入/导出/搜索测试
   - CSV/XLSX 导入。
   - append/replace 模式。
   - 导入结果摘要。
   - FAQ 导出。
   - FAQ search-test panel。

4. 批处理体验增强
   - 上传进度。
   - 部分成功/失败摘要。
   - 文档列表中可重试失败任务。

5. RBAC-lite 和 workspace 外壳
   - 登录。
   - 用户和 tenant/workspace 表。
   - 先做 Owner/Admin/Viewer。
   - KB resource ownership。
   - Viewer 隐藏写操作。
   - create/update/delete/upload/reprocess/model change 写审计日志。

6. 设置中心
   - 合并 model/retrieval/vector/system 到 WeKnora-like settings shell。
   - 增加 parser/storage 分区，即使部分 provider 只是 disabled placeholder。

v0.7 建议排除：

- 完整四角色 RBAC 矩阵和组织共享。
- OIDC。
- 高级对象存储 provider。
- GraphRAG 和 Wiki generation。

## 更长期路线

### v0.8 候选：Agent Mode MVP

- Agent 列表。
- Agent 编辑器：模型、prompt、max iterations、temperature。
- Agent chat route。
- 工具调用流式展示。
- 内置工具：knowledge search 和可选 web search。
- 第一阶段不做任意代码执行。

### v0.8/v0.9 候选：Wiki Mode MVP

- Wiki KB 类型。
- 从文档生成 Markdown wiki pages。
- Wiki browser。
- 基础页面互链。
- 后续再做图谱抽取和图谱可视化。

### v0.9+ 候选：高级解析和多模态

- MinerU / OCR parser engine。
- 图片文档导入和 VLM captioning。
- PPT 支持。
- ASR/audio import。
- 高级对象存储 provider。

### v1.0 候选：企业级对齐

- 完整 RBAC 矩阵。
- 组织/共享空间。
- Audit log UI。
- 外部数据源同步。
- CLI 和 API auth。
- Langfuse/trace 可观测性。

## 优先级表

| 优先级 | 功能 | 用户可见影响 | WeKnora 对齐度 | 建议版本 |
| --- | --- | --- | --- | --- |
| P0 | 多轮会话 | 高 | 高 | v0.6 |
| P0 | 流式回答 | 高 | 高 | v0.6 |
| P0 | 每条消息 sources + retrieval trace | 高 | 高 | v0.6 |
| P0 | 追问 query rewrite | 高 | 中/高 | v0.6 |
| P1 | 会话侧边栏操作 | 高 | 高 | v0.6 |
| P1 | 会话设置 | 中/高 | 高 | v0.6 |
| P1 | 系统状态页 | 中 | 中 | v0.6 |
| P1 | 标签/分类 | 高 | 高 | v0.7 |
| P1 | 文档预览 | 高 | 高 | v0.7 |
| P1 | FAQ 导入/导出/搜索测试 | 中/高 | 高 | v0.7 |
| P1 | 上传进度和部分失败摘要 | 中/高 | 高 | v0.7 |
| P2 | RBAC-lite | 中/高 | 高 | v0.7 |
| P2 | 设置中心整合 | 中 | 高 | v0.7 |
| P2 | 文件夹上传 | 中 | 高 | v0.7 |
| P3 | Agent Mode MVP | 高但范围大 | 高 | v0.8 |
| P3 | Wiki Mode MVP | 高但范围大 | 高 | v0.8/v0.9 |
| P3 | OCR/MinerU/image/VLM | 中/高 | 高 | v0.9 |
| P3 | 外部数据源同步 | 中/高 | 高 | v0.9+ |
| P3 | CLI/Chrome Extension/Mini Program/IM | 中 | 高 | v1.0+ |

## 建议版本叙事

v0.6 可以命名为：

> 会话化 Quick Q&A：把当前单轮 RAG 调试台升级为可持续使用的知识库聊天体验，支持多轮追问、流式回答、会话历史、来源追踪和检索解释。

v0.7 可以命名为：

> 知识管理增强与工作区基础：补齐标签、预览、FAQ 批量导入导出、批处理反馈和最小权限模型，为后续 Agent / Wiki / 多人协作打地基。

这个顺序能继续贴近 WeKnora，但不会让 knowmate 在 v1 Quick Q&A 主线还没产品化之前就过早扩散到 Agent、Wiki、IM、插件和企业协作全家桶。
