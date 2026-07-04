# knowmate 知友

knowmate 知友是一个知识库 RAG 项目，面向模型配置、知识库管理、文档解析、混合检索、快速问答和自动评测闭环。后端采用 Python / FastAPI。

当前版本为 v1.0，主线是在 v0.9/v0.91 固定 Quick Q&A 链路和 v0.92 MinerU 解析能力基础上补齐 RAGas 知识库级自动评测闭环：可从已解析 chunks 生成/保存评测集，复用知识库绑定的 QA / Embedding 模型运行 Quick Q&A，计算五项 0-1 量化指标，并在前端“评测”页面展示总分、基线对比、指标分布、逐题明细和 sources。v1.0 继续固定采用 Query Understand + over-retrieval + Qdrant dense retrieval + ParadeDB pg_search BM25 + RRF + mandatory composite rerank/MMR + parent-child context，不把 vector-only、keyword-only、rerank 开关或 planned vector backends 暴露为用户配置项。v1.0 版本说明见 [docs/v1.0.md](docs/v1.0.md)：

```text
模型管理
  -> 知识库绑定 QA / Embedding 模型
  -> 标签组织
  -> 文档上传
  -> 上传队列 / 多文件进度
  -> 解析器配置 / MinerU API Key 加密保存
  -> Celery Worker 解析文档
  -> PDF/Office/图片类文档默认走 MinerU
  -> PDF 超 200 页自动拆成 <=200 页分片并合并 Markdown
  -> Adaptive Chunking 切片
  -> 文档预览 / chunk outline
  -> 生成 embedding
  -> chunk 元数据写 PostgreSQL
  -> 向量写 Qdrant
  -> FAQ 导入导出 / FAQ 检索测试
  -> FAQ 相似问法 / FAQ 索引模式
  -> quick-answer / knowledge-search
  -> query understand / intent trace
  -> 多知识库 / 文件范围检索
  -> over-retrieval 候选池放大
  -> Qdrant 向量召回
  -> ParadeDB BM25 关键词召回
  -> low-recall query expansion
  -> RRF hybrid merge
  -> mandatory composite rerank top8
  -> MMR 去冗余
  -> parent-child / neighbor context expansion
  -> chat model 生成 answer
  -> 返回 answer + sources + retrieval trace
  -> RAGas evaluation testset / golden testset
  -> evaluation run 调用 Quick Q&A
  -> context_precision / context_recall / faithfulness / response_relevancy / factual_correctness
  -> 总分、基线对比、逐题明细和 source 命中诊断
  -> 阶段化 retrieval trace
  -> sources 显示知识库来源
  -> 保存 chat session / messages
  -> Chat mention scope
  -> 停止生成 / 自动标题 / last-request state
  -> 会话搜索 / 批量删除 / 推荐问题
  -> 文档处理 timeline
  -> 文档下载 / 取消解析 / 移动 KB
  -> runtime status / Command Palette
  -> retrieval diagnostics / rendered context
  -> history merge / rerank cleaning / MMR
  -> FAQ import progress / batch fields / FAQ boost
  -> chunk by-id / update / disable / generated questions
  -> message search / chat-history stats
  -> model providers / vector-store types
  -> composite retriever / sparse backend MVP
  -> attachment context
```

## 当前进度

已完成：

- FastAPI 后端骨架：API router、service、repository、配置、日志、健康检查。
- PostgreSQL 元数据存储：知识库、文档、chunks、租户检索配置、模型实体等表结构和 Alembic migration。
- 模型管理：
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
- 检索配置：
  - 单租户 `retrieval_config` JSON。
  - v0.9 固定模式：`retrieval_mode=hybrid`、`vector_engine=qdrant`、`keyword_engine=paradedb_bm25`。
  - v0.9 固定值：`embedding_top_k=50`、`keyword_top_k=50`、`vector_threshold=0.15`、`keyword_threshold=0.2`、`rrf_k=60`、`rrf_vector_weight=0.65`、`rrf_keyword_weight=0.35`、`rrf_top_k=30`、`rerank_top_k=8`、`rerank_threshold=0.2`、`final_context_count=6`、`max_context_chars=8000`；实际检索内部会按 `min(max(rerank_top_k * 5, 50) * scope_count, 500)` 放大候选池，再进入 RRF、mandatory composite rerank 和 MMR。
  - 用户侧不再支持 `vector_only / keyword_only / hybrid` 模式切换；Quick Q&A 固定执行混合召回和 mandatory rerank。
- v0.2.1 基础 CRUD 补齐：
  - 知识库列表、更新、软删除。
  - 文档软删除。
  - 知识库下文档列表。
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
- 文档重处理：
  - 单文档重处理。
  - 知识库批量重处理。
  - 重处理前按 `knowledge_id` 清理旧向量并替换 PostgreSQL chunks。
- 通用解析注册表：`builtin` 支持 `.txt/.md/.pdf/.docx/.csv/.json/.xlsx`。
- 自适应切分：`auto / heading / heuristic / legacy`，支持 protected blocks、context header、parent-child chunking。
- Chunking preview/debug API：可预览命中策略、profile、chunk 统计和切片内容。
- v0.4 Vue / TypeScript Dashboard：
  - 使用 Vue 3、Vite、TypeScript、Arco Design Vue、Pinia、vue-router、markdown-it 和 highlight.js。
  - 使用 hash router，生产路径形态为 `/#/chat`、`/#/knowledge-bases`、`/#/knowledge-bases/:kbId/documents`、`/#/knowledge-bases/:kbId/faqs`、`/#/settings`。
  - 从旧单文件 `App.vue` 拆分为布局、复用组件、Pinia stores、API utils、类型定义和多个业务视图。
  - 页面覆盖快速问答、知识搜索、知识库列表、文档管理、FAQ 管理、设置中心、模型配置、VectorStore、检索配置和切分预览。
  - 保持浅色企业软件界面：近白页面背景、绿色品牌主色、低饱和边框、中文企业软件观感。
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
  - query rewrite 在 v0.6 作为历史追问增强引入；当前 v0.9+ 已升级为每轮 Quick Q&A 都执行的 query understand，trace 展示 original / rewritten query、intent 和失败/回退状态。
  - 前端 `/#/chat` 升级为会话化聊天工作台：左侧会话栏、流式消息、每条 assistant 消息 sources/trace 折叠面板、基础会话设置和保留的检索调试入口。
- v0.61 平台能力补强：
  - 新增知识库标签体系：标签 CRUD、文档/FAQ 标签筛选、批量设置标签，并把 `tag_id` 写入 Knowledge、FAQEntry、Chunk 和 Qdrant payload。
  - 新增文档预览 API 和前端预览抽屉，展示摘要、正文预览、chunk outline 和 chunk 内容导航。
  - 新增 FAQ CSV/XLSX 导入导出，支持 append/replace、逐行失败摘要、metadata、enabled 和 tag_id。
  - FAQ 管理页新增导入结果卡片、导出按钮和 FAQ 检索测试抽屉。
  - 批量删除/重处理响应新增 requested/succeeded/failed/failures，任务列表新增 batch_summary，文档页展示批处理进度和失败任务重试。
  - 新增 `/#/settings` 设置中心外壳，整合模型、VectorStore、检索、解析器和存储状态；parser/storage provider 未接入项以禁用占位展示。
  - 会话列表支持搜索、批量删除；新会话空态展示来自 FAQ 和 chunk generated_questions 的推荐问题。
- v0.7 知识库工作流补强：
  - 知识库列表和详情返回 `capabilities`，支持单租户 KB pin/unpin 和置顶排序。
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
- v0.8 Quick Q&A 可解释性、检索质量和管理闭环：
  - retrieval diagnostics 细化到 rewrite、vector、keyword、RRF、parent_expand、deduplicate、FAQ merge、rerank 和 answer 阶段，前端 Chat 和检索调试面板可读展示。
  - Quick Q&A 保存 `rendered_context` 和 `prompt_context_summary`，并支持轻量 history merge。
  - Rerank 增加 passage cleaning、失败降级、阈值降级和 MMR 去冗余。
  - FAQ 导入记录 progress、last result 和 display status；FAQ 支持字段批量更新，并在检索阶段支持 FAQ merge / boost。
  - Chunk 支持 by-id 查询、更新、禁用、generated questions 管理和前端详情抽屉。
  - Chunker debug 增加策略链、被拒绝层级、保护块统计、size distribution 和 token-aware validation。
  - 新增历史问答搜索、chat-history stats、模型 provider presets、vector-store types 和 composite retriever diagnostics。
  - 新增 OpenSearch/Elasticsearch sparse/BM25 后端 MVP，当前以 fake/test-client 与配置边界验证为主；生产未配置时返回中文明确错误。
  - `/api/v1/runtime-status` 增强模型、向量库、存储 provider、parser engines 和修复建议。
  - Quick Q&A 支持临时文本附件上下文，附件只进入本轮 prompt，不写入知识库、不写入 Qdrant、不作为 sources 返回。
  - 开发启动脚本统一启动 Docker 后端栈和本机 Vite，清理本机 API / Celery 残留，避免 Windows worker 与 Linux Docker worker 混跑。
- v0.9 固定 RAG 主链路：
  - 新增集中化 v0.9 retrieval config，固定 Qdrant dense、ParadeDB BM25、RRF、mandatory rerank、parent-child chunking 和最终 context 限制。
  - 文档处理固定 parent-child：parent chunks 用于回答上下文，child chunks 写入 PostgreSQL、Qdrant 和 ParadeDB BM25 检索索引。
  - 新增 ParadeDB pg_search BM25 migration 和 repository 边界；生产 PostgreSQL keyword search 不再静默退回 simple FTS，缺少 `pg_search` 或 BM25 索引时返回中文明确错误。
  - Quick Q&A / knowledge-search 公开请求不再接收 retrieval mode；实际 trace 固定为 hybrid，并记录 vector、keyword、RRF、rerank、parent_expand、context_select 和 answer 阶段。
  - Rerank 模型为必需项；有候选命中但未配置可用 `Rerank` 模型时返回 `系统未完成 rerank 模型配置，请先在模型配置中配置可用的重排模型。`
  - Sources 补齐 `document_title`、`source_type`、`snippet`、child chunk id、parent chunk id、score、rerank score 和 metadata 摘要。
  - 前端设置页只展示 v0.9 固定主链路和 Qdrant 配置状态，不再展示 planned vector backends、retrieval mode 选择、关闭 rerank 或关闭 parent-child 的开关。
  - Docker Compose 提供完整后端栈 `postgres / redis / qdrant / api / worker`；`scripts/start-dev.ps1` 负责启动 Docker 后端和本机 Vite，不等同于自动化测试。
- v0.91 召回质量和 Chat 体验修复：
  - 修复本地运行态 embedding 维度与 Qdrant collection 不一致导致 `vector_hits=0` 的排障路径；切换 embedding 维度后必须重处理文档或保持模型配置维度与已入库向量一致。
  - Rerank composite score 增加 query lexical coverage，降低错误主题高 rerank 分压过目标条文的概率；FAQ 命中仍由 FAQ merge/boost 独立控制。
  - Quick Answer 默认 prompt 要求在上下文包含可适用规则时进行规则适用分析，不因事实没有逐字出现在上下文中就直接判定知识库不足。
  - 前端品牌统一为 `knowmate知友`，移除右下角用户头像/身份区，侧边栏“开放能力”改为“设置”。
  - Chat 消息区发送后和流式生成时自动滚到底部；用户主动上滑或滚轮离开底部时暂停自动跟随，避免回答被输入框挡住。
- v0.92 MinerU 解析和配置体验：
  - 新增独立 `parser_provider_configs` 配置表和 `/api/v1/parser-configs/mineru` API，MinerU API Key 使用后端加密保存，前端只展示已配置状态和尾号。
  - `mineru` 成为正式 parser engine；新建知识库默认把 `pdf/doc/docx/ppt/pptx/xls/xlsx/png/jpg/jpeg/jp2/webp/gif/bmp` 交给 MinerU，`txt/md/markdown/csv/json` 仍走 builtin。
  - MinerU 标准精准解析使用签名 URL 上传、异步轮询、下载结果 zip 并读取 `full.md`，解析元数据写入 `document.doc_metadata`。
  - PDF 超过 MinerU 200 页限制时，后端自动按 200 页切成临时 PDF 分片，逐片调用 MinerU，再以页码范围标题合并 Markdown，最终仍作为一个文档进入 chunk、embedding、BM25 和 Qdrant。
  - 设置中心新增“解析器”页，可配置 MinerU base URL、API Key、`vlm/ch/表格/公式/OCR` 等参数；文档上传 accept 扩展到 MinerU 支持格式。
  - 修复 DeepSeek QA 模型名称被 provider preset 重置的问题，保存 `deepseek-v4-pro` 等自定义模型名后不再回落为 `deepseek-chat`；模型测试失败时前端显示中文可读错误。
- v1.0 RAGas 评测闭环：
  - 新增知识库级评测数据模型：`evaluation_runs` / `evaluation_samples` 记录运行状态、聚合指标、逐题问题、参考答案、模型回答、sources、retrieval trace、逐题分数和脱敏模型信息。
  - 新增黄金评测集：`evaluation_testsets` / `evaluation_testset_items` 支持从已解析 chunks 生成并复用固定题集，便于同一题集下做优化前后对比。
  - 新增评测 API：`POST /api/v1/evaluations`、`GET /api/v1/evaluations`、`GET /api/v1/evaluations/{run_id}`、`POST /api/v1/evaluations/{run_id}/baseline`、`POST /api/v1/evaluations/testsets`、`GET /api/v1/evaluations/testsets`、`GET /api/v1/evaluations/testsets/{testset_id}`。
  - 新增 Celery 任务 `evaluations.run`：读取知识库 enabled chunks，生成/复用测试集，逐题调用现有 Quick Q&A 链路，再计算 `context_precision`、`context_recall`、`faithfulness`、`response_relevancy`、`factual_correctness` 五项 0-1 指标。
  - RAGas adapter 支持小批量 native RAGas；大批量默认走 `semantic_proxy` guard，避免外部 judge 长时间挂起，并把 `evaluator_config` 保存到评测运行。
  - 前端新增 `/#/evaluations` 页面、侧边栏入口和命令面板入口，展示总分、基线对比、指标条形图、逐题热力表、答案、参考答案、sources 和诊断信息。
  - 法律知识库质量优化：抽取 `law_name/article_no/article_no_normalized/part/chapter/section/item_no/knowledge_piece_index` 等法律结构化 metadata，增加 legal exact lookup、legal boost、父子来源命中诊断和更严格的法律回答 prompt。
  - 30 题基线运行 `0d160b0c-31ae-490a-a06e-2bdaaa087a8e` 总分 `0.5228`；同一法律知识库在 50 题黄金集 `26f4a44b-91f4-4479-a6a2-a42e92218e5a` 上复测两次分别为 `0.8822` 和 `0.8819`，波动 `0.0003`。
- 自动化测试：覆盖多模型 CRUD、凭据加密、知识库模型校验、重处理、检索配置、hybrid/RRF/rerank/parent-child retrieval、knowledge-search API、前端关键逻辑、API 和文档处理 payload。
- v1.0 质量验证详见下方“验证命令”、[CHANGELOG.md](CHANGELOG.md) 和 [docs/v1.0.md](docs/v1.0.md)。

暂未实现：

- 登录、RBAC、多租户隔离。
- 本地 OCR/VLM/ASR、Office 超 200 页自动拆分和离线 MinerU 部署；当前生产解析默认使用 MinerU 云端 API。
- pg_jieba、Elasticsearch/OpenSearch 集群、Milvus、Weaviate、Doris、Tencent VectorDB 等额外检索后端。
- GraphRAG、多维索引、Agent Mode、Wiki Mode。
- 云端知识服务、Ollama 拉取、VLM、ASR。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 后端 | Python 3.11+, FastAPI, Pydantic, SQLAlchemy |
| 数据库 | PostgreSQL, Alembic |
| 异步任务 | Celery, Redis |
| 向量库 | Qdrant |
| 模型接入 | OpenAI Python SDK, OpenAI-compatible API, OpenAI-compatible rerank API |
| 检索 | Qdrant dense retrieval, ParadeDB pg_search BM25, RRF, mandatory rerank, parent-child context |
| 评测 | RAGas, knowledge-base evaluation runs, golden testsets, semantic proxy guard |
| 前端 | Vue 3, TypeScript, Vite, Arco Design Vue, Pinia, vue-router, markdown-it, highlight.js |
| 测试与质量 | pytest, Ruff |

## 快速启动

如果依赖已经安装并配置好 `.env`，Windows 开发环境可优先使用一键脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-dev.ps1
```

脚本会先清理本机残留的 API / Celery / Vite 进程，再启动 `postgres / redis / qdrant / api / worker`，最后拉起本机 Vite dev server。默认路径是 `docker compose up -d` + `docker compose restart api worker`，用于快速加载挂载代码；当 `Dockerfile`、`pyproject.toml` 或 `docker-compose.yml` 变化、镜像不存在，或显式传入 `-Rebuild` 时，脚本才会执行 `docker compose up -d --build`。后端统一运行在 Docker 中，避免 Windows 本机 worker 和 Linux Docker worker 混跑导致上传文件路径不一致。v0.9 的 `postgres` 服务使用 ParadeDB PostgreSQL 16 镜像，并通过 `shared_preload_libraries=pg_search` 加载 BM25 扩展；如果扩展未加载，BM25 migration 和生产 keyword search 会明确失败。

需要强制重建镜像时，可以双击 `rebuild-dev.bat`，或运行：

```powershell
scripts/start-dev.ps1 -Rebuild
```

更新项目代码后，推荐流程是：

```powershell
git pull
scripts/start-dev.ps1
python -m pytest -q
```

`scripts/start-dev.ps1` 只负责把开发环境跑起来，不等同于完整自动化测试。需要确认代码质量时继续运行：

```powershell
ruff check .
python -m compileall app tests
npm --prefix frontend run build
```

如果本次只想手工体验页面、上传文件或确认 worker 在线，可以先只运行 `scripts/start-dev.ps1`。如果本次改动涉及后端、前端或文档处理链路，至少运行相关 pytest；涉及前端页面时再运行 `npm --prefix frontend run build`。

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

### 3. 启动后端完整栈

推荐直接用 Docker Compose 启动 PostgreSQL / Redis / Qdrant / FastAPI / Celery worker。`postgres` 使用 ParadeDB PostgreSQL 16 镜像以提供 v0.9 必需的 `pg_search`；`api` 启动时会自动执行 `alembic upgrade head`；`worker` 会等待 API 健康后再开始消费文档处理任务：

```powershell
docker compose up -d --build
```

后端地址：

- 工作台：http://127.0.0.1:8000
- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

查看 worker 日志：

```powershell
docker compose logs -f worker
```

`alembic upgrade head` 会把 PostgreSQL 表结构升级到当前代码需要的最新版本，包括模型实体、知识库模型绑定、检索配置字段、`chunks.search_text` 和 v0.9 ParadeDB BM25 索引。不执行迁移，或 PostgreSQL 未安装 `pg_search` 扩展时，后端可能会因为缺表、缺字段或缺 BM25 索引报错；Compose 的 `api` 服务已自动执行迁移。

### 4. 本机后端热重载调试

默认不要同时运行本机 API / Worker 和 Docker API / Worker。如果确实需要调试 FastAPI reload 或 Celery 本机进程，请先执行 `scripts/stop-dev.ps1` 停掉 Docker 后端，再手动启动依赖服务和本机 API / Worker：

```powershell
docker compose up -d postgres redis qdrant
alembic upgrade head
uvicorn app.main:app --reload
celery -A app.workers.celery_app:celery_app worker --loglevel=info --pool=solo
```

Celery worker 负责后台文档处理。文档上传后，解析、切分、embedding、写入 Qdrant 都由 worker 执行。不启动 worker，文档可能会停留在 `pending` 或 `processing`。

### 5. 前端开发模式

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

1. 进入 `/#/settings`，在“模型配置”分区分别配置 QA、Embedding 和必需 Rerank 模型。
2. QA 模型可选择 Qwen / DashScope、DeepSeek 或 OpenAI-compatible；Embedding 模型当前主要使用 Qwen / DashScope。
3. 填入 API Key 后点击“测试模型”。
4. 保存模型后，API Key 输入框会清空；再次测试会使用后端已加密保存的 Key。
5. 在 `/#/settings` 的“解析器”分区配置 MinerU API Key；Key 只会加密保存，页面仅显示配置状态和尾号。
6. 在 `/#/settings` 的“检索与分块”分区查看 v0.9 固定主链路：Qdrant、ParadeDB BM25、RRF、mandatory rerank、parent-child 参数和 parser/chunking 配置；可先点“切分预览”。
7. 进入 `/#/knowledge-bases` 创建知识库，知识库会绑定选择的 QA 和 Embedding 模型，并保存切分配置与解析规则。
8. 进入知识库的文档管理页，上传 `.txt/.md/.pdf/.doc/.docx/.ppt/.pptx/.xls/.xlsx/.csv/.json` 以及常见图片格式；默认文本类走 builtin，PDF/Office/图片类走 MinerU。
9. 等待 Worker 处理到“解析完成”，页面可在预览抽屉中查看摘要、outline 和 chunks；PDF 超过 200 页时后端会自动分片调用 MinerU 后合并为同一文档。
10. FAQ 知识库可进入 `/#/knowledge-bases/:kbId/faqs`，手动维护 FAQ，或使用 CSV/XLSX append/replace 导入并导出。
11. 切换向量模型、维度、解析器或切分参数后，点击“重新处理”或“重建知识库”重建向量；批量操作结果会显示成功/失败摘要。
12. 进入 `/#/chat`，选择知识库后新建会话，或从左侧会话列表继续历史会话；可搜索会话、批量删除会话，空会话会显示推荐问题。
13. 在输入区提问，页面会流式追加 assistant 消息；每条回答可展开来源依据和 retrieval trace。
14. 需要调试召回时，展开“检索调试”，只返回 sources，不调用 LLM。

## 核心 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 健康检查 |
| `GET` | `/api/v1/model-config` | 兼容接口：查询旧 active 模型配置 |
| `PUT` | `/api/v1/model-config` | 兼容接口：保存旧 active 模型配置 |
| `POST` | `/api/v1/model-config/test` | 兼容接口：测试旧模型配置 |
| `GET` | `/api/v1/models?type=Embedding` | 查询模型列表，可按类型过滤 |
| `GET` | `/api/v1/models/providers` | 查询 OpenAI-compatible provider presets 和默认模型信息 |
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
| `GET` | `/api/v1/parser-configs` | 查询解析器安全配置列表 |
| `GET` | `/api/v1/parser-configs/mineru` | 查询 MinerU 解析器安全配置，不回显 API Key |
| `PUT` | `/api/v1/parser-configs/mineru` | 保存 MinerU base URL、解析参数和可选 API Key |
| `PUT` | `/api/v1/parser-configs/mineru/credentials` | 更新 MinerU API Key |
| `DELETE` | `/api/v1/parser-configs/mineru/credentials/api_key` | 清除 MinerU API Key |
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
| `GET` | `/api/v1/knowledge-bases/{kb_id}/faqs/import-progress/{task_id}` | 查询 FAQ 导入进度 |
| `GET` | `/api/v1/knowledge-bases/{kb_id}/faqs/import-last-result` | 查询 FAQ 最近导入结果 |
| `PUT` | `/api/v1/knowledge-bases/{kb_id}/faqs/import-last-result/display-status` | 更新 FAQ 最近导入结果展示状态 |
| `PUT` | `/api/v1/knowledge-bases/{kb_id}/faqs/fields` | 批量更新 FAQ 启停、推荐、标签和 metadata 等字段 |
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
| `GET` | `/api/v1/chunks/by-id/{chunk_id}` | 按 chunk id 查询 chunk 详情 |
| `PUT` | `/api/v1/chunks/{knowledge_id}/{chunk_id}` | 更新 chunk content/search_text/metadata/is_enabled |
| `DELETE` | `/api/v1/chunks/{knowledge_id}/{chunk_id}` | 禁用 chunk 并同步向量 payload 状态 |
| `POST` | `/api/v1/chunks/by-id/{chunk_id}/questions` | 新增 chunk generated question |
| `DELETE` | `/api/v1/chunks/by-id/{chunk_id}/questions` | 删除 chunk generated question |
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
| `POST` | `/api/v1/messages/search` | 搜索历史问答消息 |
| `GET` | `/api/v1/messages/chat-history-stats` | 查询历史消息统计和可检索状态 |
| `GET` | `/api/v1/runtime-status` | 查询数据库、存储、向量库和 parser registry 运行状态 |
| `GET` | `/api/v1/tasks` | 查询任务中心 |
| `GET` | `/api/v1/tasks/{task_id}` | 查询单个任务 |
| `POST` | `/api/v1/tasks/{task_id}/retry` | 重试失败任务 |
| `GET` | `/api/v1/vector-stores` | 查询 VectorStore |
| `GET` | `/api/v1/vector-stores/types` | 查询 vector store provider 类型、字段和可用性 |
| `POST` | `/api/v1/vector-stores` | 创建 VectorStore |
| `GET` | `/api/v1/vector-stores/{id}` | 查询 VectorStore |
| `PUT` | `/api/v1/vector-stores/{id}` | 更新 VectorStore |
| `DELETE` | `/api/v1/vector-stores/{id}` | 删除 VectorStore |
| `POST` | `/api/v1/vector-stores/test` | 测试 VectorStore 配置 |

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

## v0.8 Schema / API 变化

`retrieval_trace` 增强 diagnostics：

```json
{
  "stages": [
    {
      "name": "vector",
      "status": "completed",
      "duration_ms": 18,
      "summary": "vector hits: 8",
      "input_count": 1,
      "output_count": 8
    },
    {
      "name": "faq_merge",
      "status": "completed",
      "boost_count": 1
    }
  ],
  "retrievers": [
    {
      "knowledge_base_id": "kb-id",
      "engine": "qdrant+postgres",
      "mode": "hybrid",
      "status": "completed",
      "hit_count": 5
    }
  ]
}
```

Quick Answer / Chat message 保存上下文摘要：

```json
{
  "rendered_context": "用于 prompt 的上下文正文",
  "prompt_context_summary": {
    "source_count": 5,
    "history_used": true,
    "attachments_used": 1
  }
}
```

Quick Answer 支持临时文本附件：

```json
{
  "question": "请总结附件内容",
  "attachments": [
    {
      "filename": "notes.md",
      "content_type": "text/markdown",
      "content": "# 会议纪要\n..."
    }
  ]
}
```

附件只进入本轮 prompt，不写入知识库、不写入 Qdrant，也不会作为 sources 返回。

FAQ 导入和字段批量更新新增：

```http
GET /api/v1/knowledge-bases/{kb_id}/faqs/import-progress/{task_id}
GET /api/v1/knowledge-bases/{kb_id}/faqs/import-last-result
PUT /api/v1/knowledge-bases/{kb_id}/faqs/import-last-result/display-status
PUT /api/v1/knowledge-bases/{kb_id}/faqs/fields
```

Chunk 管理新增：

```http
GET /api/v1/chunks/by-id/{chunk_id}
PUT /api/v1/chunks/{knowledge_id}/{chunk_id}
DELETE /api/v1/chunks/{knowledge_id}/{chunk_id}
POST /api/v1/chunks/by-id/{chunk_id}/questions
DELETE /api/v1/chunks/by-id/{chunk_id}/questions
```

模型、向量后端和历史消息新增：

```http
GET /api/v1/models/providers
GET /api/v1/vector-stores/types
POST /api/v1/messages/search
GET /api/v1/messages/chat-history-stats
```

## v0.9 Schema / API 变化

v0.9 将 Quick Q&A 和 knowledge-search 收敛为唯一固定主链路：

```json
{
  "retrieval_mode": "hybrid",
  "vector_engine": "qdrant",
  "keyword_engine": "paradedb_bm25",
  "embedding_top_k": 50,
  "keyword_top_k": 50,
  "rrf_top_k": 30,
  "rerank_top_k": 8,
  "enable_rerank": true,
  "enable_parent_child": true,
  "final_context_count": 6,
  "max_context_chars": 8000
}
```

`POST /api/v1/knowledge-search` 和 `POST /api/v1/quick-answer` 不再提供用户可选 `mode` 字段；旧请求体里带 `mode` 会被忽略，实际链路始终是 Qdrant 向量召回 + ParadeDB BM25 关键词召回 + RRF + mandatory rerank。

`retrieval_trace` v0.9 关键字段：

```json
{
  "query_original": "原始问题",
  "query_normalized": "标准化问题",
  "query_rewritten": "改写后问题或 null",
  "vector_hits": 50,
  "keyword_hits": 50,
  "rrf_hits": 30,
  "rerank_hits": 8,
  "selected_contexts": [
    {
      "document_id": "document-id",
      "chunk_id": "child-chunk-id",
      "parent_chunk_id": "parent-chunk-id",
      "context_index": 1
    }
  ],
  "model_config_used": {
    "embedding_model_id": "embedding-id",
    "qa_model_id": "qa-id",
    "rerank_model_id": "rerank-id"
  }
}
```

`sources` v0.9 关键字段：

```json
{
  "document_id": "document-id",
  "document_title": "文档标题",
  "chunk_id": "child-chunk-id",
  "parent_chunk_id": "parent-chunk-id",
  "source_type": "document",
  "snippet": "命中片段",
  "score": 0.73,
  "rerank_score": 0.88,
  "metadata": {}
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

启动脚本和测试命令分工如下：

- `scripts/start-dev.ps1`：智能启动 Docker 后端栈和本机 Vite；默认不重建镜像，但会重启 `api / worker` 加载挂载代码，便于手工验收页面、上传、解析和问答。
- `python -m pytest -q`：跑自动化测试，确认代码行为没有回归。
- `ruff check .` / `python -m compileall app tests` / `npm --prefix frontend run build`：做代码质量、语法和前端构建检查。

```powershell
python -m pytest -q
ruff check .
python -m compileall app tests
npm --prefix frontend run build
```

最近一次本地验证结果：

- `python -m pytest -q`：`253 passed`
- `ruff check .`：通过
- `python -m compileall app tests`：通过
- `npm --prefix frontend run build`：通过，仍有既有 Vite 大 chunk 提示。
- `python -m pytest tests/test_v10_ragas_evaluations.py tests/test_frontend_v10_evaluations.py -q`：`11 passed`
- RAGas 法律知识库 50 题黄金集复测：run `d675c9a7-4abc-4c8a-8e25-6e1d576fbc85` 总分 `0.8822`，run `0f650beb-ba66-471e-814b-48b17e5c9cb9` 总分 `0.8819`，两次波动 `0.0003`。
- 法律检索 A/B：`.runtime-logs/ab-legal-exact-v3.json` 中 `recall_at_10=0.98`、`precision_at_5=0.98`、`miss_count=1`、`failed=0`。
- Browser smoke：`http://127.0.0.1:5173/#/evaluations` 可查看评测运行、总分、五项指标、基线对比、逐题明细和 source 诊断。
- `scripts/start-dev.ps1 -Rebuild` / `rebuild-dev.bat`：强制重建完整后端栈镜像；PostgreSQL 运行 `paradedb/paradedb:pg16` 并加载 `shared_preload_libraries=pg_search`。
- 本地服务 E2E：使用真实 PostgreSQL/ParadeDB 和 Qdrant、进程内 fake Embedding/Chat/Rerank，验证知识库创建、文档上传、同步处理、parent-child chunks、Qdrant point、ParadeDB BM25 hit、knowledge-search 和 quick-answer trace/sources 均通过。
- v1.0 分项验收详见 [CHANGELOG.md](CHANGELOG.md) 的 v1.0 Verification。
- v1.0 本地服务端到端验证需要 PostgreSQL/ParadeDB `pg_search`、Redis、Qdrant、API、Celery Worker、可用 QA / Embedding / Rerank 模型配置；生产解析 PDF/Office/图片类文档还需要已配置的 MinerU API Key；真实 RAGas native judge 评测需要可用 evaluator/QA 模型和外部模型服务。

## 开发备注

- v1.0 仍默认单租户，`DEFAULT_TENANT_ID=10000`。
- Docker Compose 当前提供完整后端栈：`postgres / redis / qdrant / api / worker`。前端 dev server 仍通过 `npm --prefix frontend run dev` 或 `scripts/start-dev.ps1` 启动。
- 默认开发方式是 Docker API + Docker worker + 本机 Vite。不要同时运行本机 `uvicorn` / `celery` 和 Docker `api` / `worker`，否则上传文件路径可能在 Windows 与 Linux 容器之间不兼容。
- 文档上传后必须有 Celery Worker 在线；`scripts/start-dev.ps1` 会自动启动并重启 worker，否则文档会停留在 `pending` 或 `processing`。
- 切换 embedding 模型、维度、parser/chunking 参数或 keyword 检索文本策略后，需要重处理文档或重建知识库来刷新 PostgreSQL chunks、Qdrant 向量和 ParadeDB BM25 索引。
- 默认 keyword search 是 PostgreSQL + ParadeDB `pg_search` BM25；测试环境可使用 fake repository / injected client，生产 Quick Q&A 不会静默退回 simple FTS。
- Rerank 是 v1.0 Quick Q&A 主链路必需项；必须先创建可用的 `Rerank` 模型，并在检索配置中绑定 `rerank_model_id`，否则有候选命中时 Quick Q&A 返回中文明确错误。
- MinerU 云端解析已接入；PDF/Office/图片类文档会发送到 MinerU，PDF 超过 200 页会自动本地分片后逐片解析，非 PDF 超限仍需人工拆分或后续转换为 PDF 再处理。
- RAGas 评测复用知识库绑定的 QA / Embedding 模型，API Key 只在后端解密使用；评测运行只返回模型名、provider、是否配置和 `api_key_last4`，不会回传明文或密文。
- 大批量评测默认 `RAGAS_EVALUATOR_MODE=auto`，超过 `RAGAS_NATIVE_MAX_ROWS=20` 时使用 `semantic_proxy` 计算可重复指标；需要强制 native judge 时再显式设置 `RAGAS_EVALUATOR_MODE=native` 并控制题量。
- 模型测试会透传 provider 的真实错误，例如认证失败、模型不存在、维度不匹配等，前端会渲染中文可读文本，不渲染 `[object Object]`；DeepSeek 自定义模型名保存后不会被 provider preset 重置。
- 生产部署前需要更换默认数据库密码，固定并妥善保存 `MODEL_CONFIG_ENCRYPTION_KEY`，并增加鉴权和访问控制。

## 版本记录

见 [CHANGELOG.md](CHANGELOG.md)。
