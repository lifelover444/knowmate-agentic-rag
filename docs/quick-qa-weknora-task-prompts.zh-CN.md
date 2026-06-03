# knowmate Quick Q&A 对标 WeKnora TASK 提示词

日期：2026-06-03

用途：本文件用于在新的 Codex 对话里逐个复制 TASK 提示词执行。范围只包含会影响 Quick Q&A 质量、解释性、检索能力、入库质量和管理闭环的任务。

明确排除：

- Auth / RBAC-lite / 登录鉴权 / 用户体系 / tenant member / ownership。
- Organization / Share。
- Agent Mode / MCP / Skills。
- Wiki Mode / GraphRAG 完整实现。
- IM、多端、CLI、MCP server、Chrome Extension、小程序。
- 完整对象存储 provider 实现。
- 完整 DocReader / MinerU / WeKnoraCloud parser 实现。

这些排除项不代表不重要，只是不直接阻塞 Quick Q&A 答案质量。

## 通用开场提示词

每个新对话建议先发送下面这一段，再追加具体 TASK。

```text
你在 D:\myproject\knowmate-agentic-rag 工作。

请严格遵守 AGENTS.md：knowmate 必须作为 FastAPI/Python 技术栈下对 Tencent/WeKnora 的近似复现；实现前先对照 D:\myproject\_references\WeKnora 的对应模块，不要发明 unrelated RAG 产品。

本轮只做我给出的单个 TASK，不要顺手做 Auth/RBAC-lite、Agent、Wiki、IM、DataSource、CLI/MCP server 或大范围重构。

要求：
1. 先阅读相关 knowmate 代码和 WeKnora 参考代码。
2. 保持 API handler thin，业务逻辑放 services/repositories/RAG/integrations。
3. 涉及 schema 变化必须加 Alembic migration。
4. 先补/改最小相关测试，再实现。
5. 完成后运行最小相关测试；有前端变更则运行 npm --prefix frontend run build；后端变更至少运行 python -m compileall app tests。
6. 不使用真实外部 API key；测试用 fake client / injected test client。
7. 前端错误必须是中文可读文本，不渲染 [object Object]。
8. API key 和敏感配置不得明文返回或记录日志。
```

## 推荐执行顺序

建议按顺序执行。后面的任务会默认前面的数据结构或 API 已存在。

1. TASK-025 到 TASK-030：检索 trace、上下文、rerank，是答案质量和可解释性的核心。
2. TASK-031 到 TASK-033：FAQ 问答质量闭环。
3. TASK-034 到 TASK-038：chunk 管理、generated questions、chunk debug 和 token-aware chunking。
4. TASK-039 到 TASK-043：消息搜索、模型/provider、vector store 类型、composite retriever 和 sparse 后端。
5. TASK-044 到 TASK-045：运行状态真实化和附件上下文。

## TASK-025 Retrieval Diagnostics 后端基础

```text
TASK-025：为 knowmate Quick Q&A 增加 WeKnora-style retrieval diagnostics 后端基础。

目标：
- 当前 QuickAnswerService 的 retrieval_trace 只有 rewrite/search/rerank/answer 粗粒度阶段。
- 请将 KnowledgeSearchService.search 的内部检索过程改造成可以返回 hits + diagnostics。
- diagnostics 至少包含 vector、keyword、rrf、parent_expand、deduplicate、rerank 的阶段信息。
- 每个阶段包含：name、status、duration_ms、input summary、output summary、error_message。
- quick-answer 和 quick-answer/stream 的 response/message retrieval_trace 使用这些 diagnostics。

边界：
- 不做前端 UI，本任务只做后端和测试。
- 不重写成完整 WeKnora chat_pipeline。
- 不引入新检索后端。
- 保持旧 response shape 兼容，新增字段只能是向后兼容。

参考：
- knowmate：app/services/quick_answer.py、app/services/knowledge_search.py、app/rag/retriever/__init__.py
- WeKnora：D:\myproject\_references\WeKnora\internal\application\service\chat_pipeline\search.go、search_parallel.go、rerank.go

验收：
- quick-answer 非流式返回 trace.stages，且 stages 内可看到 vector/keyword/RRF/parent/rerank 的真实状态。
- hybrid 模式能同时报告 vector 和 keyword 命中数量。
- vector_only / keyword_only 不适用阶段标记为 skipped。
- 无命中时 answer 阶段标记 skipped，错误信息中文可读。

建议验证：
- python -m pytest tests/test_quick_answer.py tests/test_v03_knowledge_search.py -q
- python -m pytest tests/test_v06_quick_answer_stream.py -q
- python -m compileall app tests
- ruff check app tests
```

## TASK-026 Retrieval Trace 前端可解释展示

```text
TASK-026：前端展示 TASK-025 的阶段化 retrieval trace。

目标：
- Chat 页面和 Source/Trace 展示区域显示 rewrite、vector、keyword、rrf、parent_expand、deduplicate、rerank、answer 阶段。
- 每个阶段展示状态、耗时、命中数/候选数/过滤数摘要。
- 对 skipped、failed、done 使用清晰中文文案。
- 保持现有 sources 展示不回退。

边界：
- 不改变后端。
- 不做新的图表库。
- 不做 Agent/tool trace。

参考：
- frontend/src/views/ChatView.vue
- frontend/src/components/SourceCard.vue
- frontend/src/types/api.ts
- WeKnora 前端可参考：D:\myproject\_references\WeKnora\frontend\src\utils\knowledgeTrace.ts、frontend/src/views/chat/components/tool-results/RelatedChunks.vue

验收：
- 流式回答完成后能看到阶段化 trace。
- trace 缺字段时 UI 安全降级，不显示 [object Object]。
- 中英文字段值转成中文说明。

建议验证：
- python -m pytest tests/test_frontend_v06_chat.py tests/test_frontend_v071_observability_status.py -q
- npm --prefix frontend run build
```

## TASK-027 Rendered Context 持久化

```text
TASK-027：为 Quick Q&A 保存 rendered_context / prompt_context_summary，补齐 WeKnora rendered_content 思路。

目标：
- 在 ChatMessage 或相关表中保存本次回答实际送入 LLM 的检索上下文摘要。
- 保存内容必须避免过大：可以保存完整 rendered_context 的截断版，以及 prompt_context_summary。
- retrieval_trace 中记录 context_chunk_ids、context_char_count、truncated。
- 前端消息详情/trace 中能展示“本次送入模型的上下文摘要”。

边界：
- 不保存 API key、完整 prompt system secret 或敏感模型配置。
- 不做完整 WeKnora Message.rendered_content 迁移兼容，只在 knowmate 内部实现等价能力。
- 不改变用户可见 answer 和 sources 的既有字段。

参考：
- knowmate：app/db/models.py ChatMessage、app/services/chat.py、app/services/quick_answer.py
- WeKnora：D:\myproject\_references\WeKnora\internal\types\message.go 中 RenderedContent

验收：
- 新增 migration。
- 非流式和流式回答均保存 context summary。
- 无命中时 summary 为空但状态可解释。
- 前端能显示摘要，不展示原始对象。

建议验证：
- python -m pytest tests/test_v06_chat_sessions.py tests/test_v06_quick_answer_stream.py -q
- python -m pytest tests/test_frontend_v06_chat.py -q
- alembic upgrade head
- python -m compileall app tests
- npm --prefix frontend run build
```

## TASK-028 多轮 History Merge

```text
TASK-028：增强 Quick Q&A 多轮问答上下文，加入轻量 history merge。

目标：
- 当前历史主要用于 query rewrite；回答 prompt 仍以当前 query + 当前检索结果为主。
- 实现 WeKnora-like 的轻量 history merge：根据最近 N 轮 user/assistant 消息生成可控长度的 conversation context。
- conversation context 与 retrieved context 分区进入 prompt。
- retrieval_trace 记录 history_used、history_message_count、history_char_count、truncated。

边界：
- 不实现长期 memory。
- 不把所有历史无脑塞入 prompt。
- 不做 message 向量化。
- 不改变无 history 时的行为。

参考：
- knowmate：app/services/quick_answer.py、app/rag/prompt.py、app/services/chat.py
- WeKnora：D:\myproject\_references\WeKnora\internal\application\service\chat_pipeline\load_history.go、merge_history.go

验收：
- 追问场景中，回答 prompt 能包含最近对话摘要。
- 超长历史被截断并记录 trace。
- query rewrite 失败时 history merge 仍可工作。

建议验证：
- python -m pytest tests/test_v06_chat_sessions.py tests/test_v06_quick_answer_stream.py -q
- 新增/更新多轮追问单测
- python -m compileall app tests
```

## TASK-029 Rerank Passage Cleaning 和失败降级

```text
TASK-029：增强 RerankPipeline，加入 WeKnora-style passage cleaning 和失败 fallback。

目标：
- rerank 前清洗 markdown 噪声、链接、代码围栏、表格结构噪声和过长空白。
- rerank API 失败时不要让 Quick Q&A 整体失败；fallback 到原始检索结果，并在 trace 中记录 rerank_failed/fallback。
- direct load 或文件 scope 精确命中的候选可以跳过 rerank 或保持高优先级。

边界：
- 不改模型管理 UI。
- 不做 MMR，本任务只做 cleaning + fallback。
- 保持“没有配置 Rerank 模型但用户强制启用”时仍返回清晰中文错误；只有 API 调用失败才 fallback。

参考：
- knowmate：app/rag/retriever/__init__.py、app/services/knowledge_search.py
- WeKnora：D:\myproject\_references\WeKnora\internal\application\service\chat_pipeline\rerank.go 的 cleanPassageForRerank 和 fallback 逻辑

验收：
- rerank client 抛异常时 Quick Answer 仍返回答案和 sources。
- trace 明确显示 rerank failed + fallback。
- passage cleaning 有单测覆盖 markdown link、table、code block、raw URL。

建议验证：
- python -m pytest tests/test_v03_retriever.py tests/test_v03_knowledge_search.py tests/test_quick_answer.py -q
- python -m compileall app tests
- ruff check app tests
```

## TASK-030 Rerank 阈值降级和 MMR 去冗余

```text
TASK-030：为 rerank 增加阈值降级和 MMR 去冗余。

目标：
- 当 rerank 返回结果为空且阈值较高时，按 WeKnora 思路降级阈值重试或保留 top1 fallback。
- rerank 后增加 MMR 去冗余，减少多个相邻 chunk 或同内容 chunk 挤占上下文。
- trace 记录 original_threshold、degraded_threshold、mmr_input_count、mmr_output_count。

边界：
- 不改 rerank provider。
- 不影响未启用 rerank 的路径。
- MMR 参数先放 retrieval_config 默认值或内部常量，避免过度 UI。

参考：
- knowmate：app/rag/retriever/__init__.py、app/schemas/retrieval.py、app/services/retrieval_config.py
- WeKnora：D:\myproject\_references\WeKnora\internal\application\service\chat_pipeline\rerank.go 中 threshold_degrade、applyMMR

验收：
- rerank 阈值过高导致全过滤时，不再直接空结果。
- 相似 chunk 会被 MMR 降低重复度。
- trace 能解释阈值降级和 MMR 输出。

建议验证：
- python -m pytest tests/test_v03_retriever.py tests/test_v03_knowledge_search.py -q
- python -m compileall app tests
```

## TASK-031 FAQ Import Progress 和 Last Result

```text
TASK-031：补齐 WeKnora-style FAQ import progress 和 last import result。

目标：
- FAQ 导入支持任务进度查询，返回 total、processed、succeeded、failed、status、error summary。
- KB 或 FAQ 管理页能显示 last import result，包括成功数、失败数、失败行摘要、导入时间、是否已读/是否显示。
- 增加 display status API，允许用户关闭 last result 提示。

边界：
- 不做权限。
- 不改现有 CSV/XLSX 导入格式，除非为了记录 progress 必须最小扩展。
- 不要求 Celery 真异步导入；如果当前导入是同步，也要产出一致的 progress/result 结构。

参考：
- knowmate：app/services/faq_import_export.py、app/api/v1/faqs.py、app/db/models.py
- WeKnora：D:\myproject\_references\WeKnora\internal\types\faq.go、internal\router\router.go FAQ import progress route

验收：
- 导入后刷新页面仍能看到 last import result。
- 失败行摘要不会丢失。
- 用户关闭后不再显示提示，但历史结果仍可通过 API 读取。

建议验证：
- python -m pytest tests/test_v07_faq_import_export.py tests/test_v05_faq.py -q
- python -m pytest tests/test_frontend_v07_faq_import_export.py -q
- alembic upgrade head
- python -m compileall app tests
- npm --prefix frontend run build
```

## TASK-032 FAQ 字段批量更新

```text
TASK-032：增加 FAQ fields batch update，补齐 WeKnora FAQ 管理能力。

目标：
- 支持批量更新 FAQ enabled、recommended/is_recommended、tag_id 等字段。
- 前端 FAQ 列表支持多选批量启用/停用、批量标签、批量推荐状态。
- 更新后按需重建 FAQ 索引，确保检索结果同步。

边界：
- 不做权限。
- 不做复杂导入模板变化。
- 不破坏现有单条 FAQ CRUD。

参考：
- knowmate：app/services/faq.py、app/api/v1/faqs.py、frontend/src/views/FAQView.vue
- WeKnora：D:\myproject\_references\WeKnora\internal\router\router.go 中 FAQ entries/fields、entries/tags

验收：
- 批量停用后知识搜索不再返回这些 FAQ。
- 批量标签后 FAQ 和对应 chunk/vector payload 标签同步。
- 部分失败时返回中文失败摘要。

建议验证：
- python -m pytest tests/test_v05_faq.py tests/test_v07_faq_similar_indexing.py tests/test_v07_tags.py -q
- python -m pytest tests/test_frontend_v07_faq_similar_indexing.py -q
- python -m compileall app tests
- npm --prefix frontend run build
```

## TASK-033 FAQ Merge / Boost 独立策略

```text
TASK-033：在 Quick Q&A 检索阶段加入 FAQ merge / boost 独立策略。

目标：
- 当 scope 中包含 FAQ KB 或 FAQ chunks 时，不再只把 FAQ 当普通 chunk。
- 对 FAQ 标准问题、相似问法、答案 chunk 进行独立排序/boost。
- FAQ 精确或高分命中时，在最终 sources 中靠前，并在 trace 中记录 faq_merge。
- source metadata 显示 matched_question、standard_question、question_role。

边界：
- 不引入 Agent。
- 不改变 FAQ 索引模式的现有配置语义。
- 不让 FAQ 结果无条件压过文档；只在高置信命中时 boost。

参考：
- knowmate：app/services/knowledge_search.py、app/services/faq.py、app/rag/retriever/__init__.py
- WeKnora：D:\myproject\_references\WeKnora\internal\application\service\chat_pipeline\merge_faq.go、rerank.go faq_boost

验收：
- FAQ question_only / question_answer 两种模式下检索表现符合配置。
- 相似问法命中时 source 显示 matched_question。
- trace 包含 faq_merge 输入数、输出数、boost 数。

建议验证：
- python -m pytest tests/test_v07_faq_similar_indexing.py tests/test_v03_knowledge_search.py tests/test_quick_answer.py -q
- python -m compileall app tests
```

## TASK-034 Chunk by-id / Update / Disable 后端 API

```text
TASK-034：补齐 WeKnora-style chunk 管理后端 API。

目标：
- 增加 chunk by-id 查询。
- 增加 chunk update：content、search_text、metadata、enabled 状态。
- 增加 chunk delete/soft-delete 或 disable 能力。
- chunk 更新后同步 keyword metadata，并明确是否需要重建 vector；如果内容变化，应触发重嵌入或返回需要重建状态。

边界：
- 不做前端 UI。
- 不做权限。
- 不一次性实现 generated questions，那个放 TASK-035。

参考：
- knowmate：app/db/repositories/chunk.py、app/api/v1/documents.py、app/schemas/document.py
- WeKnora：D:\myproject\_references\WeKnora\internal\router\router.go RegisterChunkRoutes

验收：
- GET /api/v1/chunks/by-id/{id} 或兼容路径可查单个 chunk。
- PUT 更新 chunk 后文档 chunks 列表返回新内容。
- disable 后 quick-answer 不再召回该 chunk。

建议验证：
- python -m pytest tests/test_document_processing_chunk_payload.py tests/test_v03_knowledge_search.py -q
- 新增 chunk API 单测
- python -m compileall app tests
```

## TASK-035 Generated Questions 后端和索引

```text
TASK-035：为 document chunks 增加 generated questions 数据结构、索引和管理 API。

目标：
- chunk metadata 支持 generated_questions。
- 可以手动为 chunk 增删 generated question。
- 检索时 generated questions 可进入 search_text / embedding payload，提升召回。
- 推荐问题 API 优先利用 generated_questions。

边界：
- 不调用真实 LLM 自动生成问题；本任务只做存储、索引、API 和检索利用。
- 不做前端 UI，前端放 TASK-036。

参考：
- knowmate：app/db/models.py Chunk、app/services/chat.py recommended questions、app/services/document_processing.py
- WeKnora：D:\myproject\_references\WeKnora\internal\types\faq.go GeneratedQuestion、RegisterChunkRoutes delete generated question

验收：
- 为 chunk 添加 generated question 后，相关查询能命中该 chunk。
- 删除 generated question 后不会继续影响检索。
- 推荐问题接口能返回 generated questions。

建议验证：
- python -m pytest tests/test_v07_chat_experience.py tests/test_v03_knowledge_search.py -q
- alembic upgrade head
- python -m compileall app tests
```

## TASK-036 Chunk 管理前端

```text
TASK-036：前端增加 chunk 详情、编辑、启停和 generated questions 管理。

目标：
- 文档预览/Chunk 抽屉中可打开单个 chunk 详情。
- 支持编辑 chunk 内容或 search_text，支持启用/停用。
- 支持查看、添加、删除 generated questions。
- 明确提示“内容变化后需要重建 embedding / 已触发重建”。

边界：
- 不做批量 chunk 编辑。
- 不做权限。
- 不改文档上传流程。

参考：
- frontend/src/views/DocumentsView.vue
- frontend/src/components/ChunkPreview.vue
- frontend/src/stores/knowledgeBase.ts
- WeKnora 前端 chunk detail/tool results 可参考 D:\myproject\_references\WeKnora\frontend\src\views\chat\components\tool-results\ChunkDetail.vue

验收：
- 用户能从文档预览进入 chunk 详情并修改启停状态。
- generated questions 的新增/删除有中文反馈。
- API 错误不会显示 [object Object]。

建议验证：
- python -m pytest tests/test_frontend_v07_document_preview.py -q
- npm --prefix frontend run build
```

## TASK-037 Chunk Debug UI 增强

```text
TASK-037：增强 chunker preview/debug UI，对齐 WeKnora KBChunkingDebug。

目标：
- chunk preview 展示 selected tier、tier chain、rejected tiers、rejection reason。
- 展示 document profile：heading counts、form feed、chapter markers、tables/code、detected languages。
- 展示 chunk size stats：avg/min/max/stddev、chunk count。
- 每个 chunk card 展示 context_header、start/end、approx tokens、content preview。

边界：
- 不改 chunker 核心算法，除非发现 diagnostics 字段缺失。
- 不做真实入库。

参考：
- knowmate：app/rag/chunker.py、app/api/v1/chunker.py、frontend/src/components/ChunkPreview.vue、KnowledgeBaseDetailView settings
- WeKnora：D:\myproject\_references\WeKnora\docs\CHUNKING.md、frontend/src/views/knowledge/settings/KBChunkingDebug.vue

验收：
- KB 设置页能用样本文本看到完整 diagnostics。
- 空文本/超长文本/无结构文本都有可读提示。

建议验证：
- python -m pytest tests/test_chunker_preview_api.py tests/test_chunker.py -q
- python -m pytest tests/test_frontend_chunking_settings.py -q
- npm --prefix frontend run build
```

## TASK-038 Token-aware Chunking Validation

```text
TASK-038：补齐 token-aware chunking validation 和测试。

目标：
- token_limit 对 chunk_size 的影响更接近 WeKnora。
- 为中英文/混合语言、长英文单词、密集中文、表格、代码块增加测试。
- validator 记录 token_limit 生效原因和 fallback tier。
- preview API 返回 token stats。

边界：
- 不引入重量 tokenizer 依赖，除非项目已有合适依赖。
- 不破坏现有 chunk_size/overlap 行为。

参考：
- knowmate：app/rag/chunker.py
- WeKnora：D:\myproject\_references\WeKnora\internal\infrastructure\chunker\tokens.go、strategy_token_test.go、validator.go

验收：
- token_limit 小于默认时 chunk 不超过合理估算上限。
- protected blocks 不被 token limit 粗暴拆坏。
- diagnostics 能说明 token limit 生效。

建议验证：
- python -m pytest tests/test_chunker.py tests/test_chunker_preview_api.py -q
- python -m compileall app tests
```

## TASK-039 Message Search 和 Chat History Stats

```text
TASK-039：补齐 WeKnora-style message search 和 chat-history stats 的 Quick Q&A 相关部分。

目标：
- 增加消息搜索 API：按关键词搜索会话消息，并按 Q/A 对或 session 分组返回。
- 增加 chat-history stats：会话数、消息数、最近更新时间、可检索状态。
- 前端 Chat 侧栏或 Command Palette 可以搜索历史回答。

边界：
- 不做 message 向量化。
- 不做 chat history KB。
- 不做用户权限。

参考：
- knowmate：app/db/repositories/chat.py、app/services/chat.py、app/api/v1/chat_sessions.py、frontend/src/stores/chat.ts
- WeKnora：D:\myproject\_references\WeKnora\internal\types\message.go MessageSearchParams、RegisterMessageRoutes

验收：
- 搜索“关键词”能找到历史 user/assistant 消息。
- 结果展示 session title、query、answer snippet、created_at。
- 空结果显示中文空状态。

建议验证：
- python -m pytest tests/test_v06_chat_sessions.py tests/test_v07_chat_experience.py -q
- python -m pytest tests/test_frontend_v07_chat_experience.py tests/test_frontend_v071_command_palette.py -q
- npm --prefix frontend run build
```

## TASK-040 Model Providers 和模型分组

```text
TASK-040：增强模型管理，使 Quick Q&A 模型配置更接近 WeKnora。

目标：
- 增加 /api/v1/models/providers，返回 OpenAI-compatible provider presets。
- 模型列表和设置页按 KnowledgeQA / Embedding / Rerank 分组。
- 创建模型时可以从 provider preset 填充 base_url、provider、默认模型名。
- 敏感字段只显示 configured/last4。

边界：
- 不做 Ollama 下载。
- 不做 WeKnoraCloud。
- 不做 VLM/ASR。
- 不做登录权限。

参考：
- knowmate：app/api/v1/models.py、app/services/model_config.py、frontend/src/views/ModelSettingsView.vue
- WeKnora：D:\myproject\_references\WeKnora\internal\handler\model.go、config\builtin_models.yaml.example

验收：
- providers API 有稳定响应。
- 前端模型设置区分 QA/Embedding/Rerank。
- API key 不明文回显。

建议验证：
- python -m pytest tests/test_model_config.py tests/test_frontend_v02_model_management.py -q
- npm --prefix frontend run build
- python -m compileall app tests
```

## TASK-041 Vector Store Types 和可用性状态

```text
TASK-041：补齐 vector-store /types 和 provider 可用性状态。

目标：
- 增加 /api/v1/vector-stores/types，返回 qdrant 可用，OpenSearch/Elasticsearch/Milvus/Weaviate/Doris/Tencent VectorDB 标记 unavailable 或 planned。
- 每个 type 返回 connection_fields、index_fields、sensitive 标记、默认值。
- 前端 VectorStore 设置页使用 types API 渲染说明。

边界：
- 不实现除 Qdrant 外的真实后端。
- 非 Qdrant 创建时返回清晰中文错误。
- 不明文回显敏感字段。

参考：
- knowmate：app/integrations/vector_store.py、app/api/v1/vector_stores.py、frontend/src/views/VectorStoreSettingsView.vue
- WeKnora：D:\myproject\_references\WeKnora\internal\types\vectorstore.go GetVectorStoreTypes

验收：
- types API 与前端设置页都能展示 planned providers。
- Qdrant 现有测试不回退。
- 非 Qdrant 创建失败信息明确。

建议验证：
- python -m pytest tests/test_v05_vector_stores.py tests/test_frontend_v03_retrieval.py -q
- npm --prefix frontend run build
- python -m compileall app tests
```

## TASK-042 Composite Retriever 接口

```text
TASK-042：抽象 composite retriever 接口，为后续多后端 fan-out 做准备。

目标：
- 将当前 KnowledgeSearchService 中 per-KB 检索和 retriever build 逻辑整理为小接口。
- 支持一个 KB 绑定一个 retriever engine，多个 KB fan-out 后统一 merge。
- diagnostics 能记录每个 KB / retriever engine 的命中、耗时、错误。
- 当前仍只实现 Qdrant + PostgreSQL keyword。

边界：
- 不新增真实后端。
- 不做大范围 pipeline 重写。
- 不改变 QuickAnswer API。

参考：
- knowmate：app/services/knowledge_search.py、app/rag/retriever/__init__.py
- WeKnora：D:\myproject\_references\WeKnora\internal\application\service\retriever\composite.go、factory.go、registry.go

验收：
- 多 KB scope 结果和 TASK-014 兼容。
- diagnostics 能按 KB 展示 fan-out。
- 单 KB 行为不变。

建议验证：
- python -m pytest tests/test_v07_multi_scope_retrieval.py tests/test_v03_knowledge_search.py tests/test_quick_answer.py -q
- python -m compileall app tests
```

## TASK-043 OpenSearch 或 Elasticsearch Sparse/BM25 后端 MVP

```text
TASK-043：接入第一个真实 sparse/BM25 后端 MVP，优先 OpenSearch；如果项目环境更适合 Elasticsearch，可选 Elasticsearch。

目标：
- 在 vector store/retriever 边界增加 OpenSearch 或 Elasticsearch keyword/sparse 检索实现。
- 支持文档处理时写入文本索引，删除/移动/标签更新时同步。
- retrieval mode keyword_only/hybrid 可选择该后端。
- 如果服务未配置，返回清晰 unavailable 状态，不静默 fallback。

边界：
- 只接一个后端，不同时接多个。
- 不要求 CI 依赖真实 OpenSearch/Elasticsearch，自动测试用 fake client。
- 不影响默认 Qdrant + PostgreSQL fallback。

参考：
- knowmate：app/integrations/vector_store.py、app/services/document_processing.py、app/rag/retriever/__init__.py
- WeKnora：D:\myproject\_references\WeKnora\internal\application\service\retriever\keywords_vector_hybrid_indexer.go、internal\types\vectorstore.go

验收：
- fake client 测试覆盖 upsert/search/delete。
- 未配置服务时 Quick Q&A 给出明确中文错误或 unavailable。
- hybrid trace 能区分 keyword engine。

建议验证：
- python -m pytest tests/test_v05_vector_stores.py tests/test_v03_retriever.py tests/test_v03_knowledge_search.py -q
- python -m compileall app tests
- ruff check app tests
```

## TASK-044 Runtime Status 真实化

```text
TASK-044：增强 runtime-status，把 parser/storage/model/vector 状态做成 Quick Q&A 运维可用。

目标：
- runtime-status 返回 database、local storage、qdrant、parser engines、model configs、vector stores 的真实检查结果。
- parser engines 区分 builtin available、ocr/mineru/docreader unavailable/planned。
- storage 区分 local available 和对象存储 planned/unconfigured。
- 前端 Settings 页面显示这些状态和修复建议。

边界：
- 不实现对象存储。
- 不实现 DocReader/MinerU。
- 不做登录权限。

参考：
- knowmate：app/api/v1/runtime_status.py、app/api/v1/parser_engines.py、frontend/src/views/SettingsView.vue
- WeKnora：D:\myproject\_references\WeKnora\internal\router\router.go RegisterSystemRoutes

验收：
- 服务未启动或 Qdrant 不可达时状态可读。
- 设置页不再依赖静态占位。
- 所有错误中文可读。

建议验证：
- python -m pytest tests/test_v071_observability_status.py tests/test_frontend_v071_observability_status.py -q
- npm --prefix frontend run build
- python -m compileall app tests
```

## TASK-045 Attachment Context MVP

```text
TASK-045：实现 Quick Q&A 附件上下文 MVP，先支持文本类附件作为本轮 prompt 临时上下文。

目标：
- Chat 输入支持上传 txt/md/csv/json 小文件作为本轮临时附件。
- 后端解析附件文本，限制大小和行数，构造成 <attachments> prompt section。
- 附件不写入长期知识库，不进入 Qdrant。
- ChatMessage 保存 attachment metadata 和是否截断。
- rendered_context / retrieval_trace 记录 attachments_used。

边界：
- 不支持图片/OCR/PDF/docx。
- 不做对象存储 provider；可使用现有 local/runtime 临时文件机制。
- 不做 Agent tool attachment。
- 不把附件内容泄露到 sources。

参考：
- knowmate：frontend/src/views/ChatView.vue、app/services/chat.py、app/services/quick_answer.py、app/rag/prompt.py
- WeKnora：D:\myproject\_references\WeKnora\internal\types\message.go MessageAttachment、MessageAttachments.BuildPrompt

验收：
- 用户上传一个 txt 附件后提问，答案能引用附件内容。
- 超大小文件返回中文错误。
- 附件内容截断时前端显示截断提示。
- 不配置模型时仍返回现有清晰模型配置错误。

建议验证：
- python -m pytest tests/test_v06_chat_sessions.py tests/test_v06_quick_answer_stream.py -q
- python -m pytest tests/test_frontend_v06_chat.py -q
- npm --prefix frontend run build
- python -m compileall app tests
```

## 批量执行提示

如果想在一个新对话中连续跑一小批，建议最多一次给 3 个 TASK，例如：

```text
请按顺序执行 TASK-025、TASK-026、TASK-027。每完成一个 TASK 后先运行对应验证并更新 docs/ai-loop/done.md，再进入下一个 TASK。不要跳过失败测试，不要把 3 个 TASK 混成一个大改。
```

更推荐一个对话只跑一个 TASK。这样更容易 review diff，也更符合当前项目的单任务循环。

## 完成后的统一收尾

每个 TASK 完成后，要求新对话里的 Codex 做：

```text
请把完成记录追加到 docs/ai-loop/done.md，并在最终回复里说明：
- 完成了哪个 TASK；
- 修改了哪些文件；
- 跑了哪些验证命令和结果；
- 哪些后续 TASK 仍未做；
- 是否有未解决风险。
```

