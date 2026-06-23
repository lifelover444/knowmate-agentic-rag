# AI Done Log

### 2026-06-21 | v0.92 | MinerU 解析、PDF 自动分片和模型配置修复归档
- summary: 将解析模块升级归档为 `v0.92`：新增独立 parser provider 配置表和 `/api/v1/parser-configs` API，MinerU API Key 加密保存且前端只显示配置状态/尾号；接入 MinerU 标准精准解析，本地文件经签名 URL 上传、异步轮询、下载 zip 并读取 `full.md`；默认文档/Office/图片类解析走 MinerU，文本类仍走 builtin；PDF 超 200 页时自动按 200 页生成临时分片、逐片调用 MinerU、按页码范围合并 Markdown 并写入 `mineru_split/page_count/mineru_parts` 元数据；修复 DeepSeek 自定义模型名保存后被 preset 重置和模型测试失败仍显示成功的问题；记录下一阶段 RAG 量化评测方向。
- files: `README.md`, `CHANGELOG.md`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`, `app/api/v1/parser_configs.py`, `app/services/parser_config.py`, `app/integrations/mineru.py`, `app/integrations/pdf_splitter.py`, `app/services/document_processing.py`, `frontend/src/views/ParserSettingsView.vue`, `frontend/src/components/ModelConfigForm.vue`, `frontend/src/views/ModelSettingsView.vue`, `tests/test_mineru_integration.py`, `tests/test_frontend_v02_model_management.py`
- verification: `python -m pytest tests/test_mineru_integration.py -q` -> 8 passed；`python -m pytest tests/test_mineru_integration.py tests/test_document_processing_chunk_payload.py tests/test_v07_processing_spans.py -q` -> 17 passed；`python -m pytest -q` -> 233 passed；`ruff check .` -> All checks passed；`python -m compileall app tests` -> exit 0；`npm --prefix frontend run build` -> passed with existing Vite large chunk warning；Browser mock smoke 确认 `deepseek-v4-pro` 保存后不回落为 `deepseek-chat`，模型测试失败显示 error message。
- follow_ups: 下一阶段优先建设可重复 RAG eval 闭环：维护问题集、计算 retrieval Recall@K/MRR/nDCG、source hit rate、answer faithfulness/relevancy，并评估 DeepEval/Ragas/Phoenix 接入；非 PDF 超 200 页拆分、离线 MinerU、本地 OCR/VLM/ASR 继续保留为后续解析增强。

### 2026-06-17 | v0.91 | 召回质量和 Chat 体验修复归档
- summary: 将真实运行态召回排障和前端交互优化归档为 `v0.91`：记录 embedding 维度与 Qdrant collection 不一致导致 `vector_hits=0` 的根因；说明 rerank composite score 新增 `lexical_score`、FAQ 仍由 FAQ merge/boost 控制、parent chunk 不进入初始检索候选；同步 Quick Answer prompt 从“过度保守”改为可基于上下文规则做适用分析；记录 Chat 前端品牌 `knowmate知友`、侧边“设置”、移除右下角身份区、发送和流式生成自动滚动到底部且用户上滑暂停跟随。
- files: `README.md`, `CHANGELOG.md`, `docs/quick-answer-weknora-aligned-chain-2026-06-10.zh-CN.md`, `docs/ai-loop/done.md`
- verification: 文档记录同步到 v0.91；对应代码验证已完成：`python -m pytest -q` -> 220 passed；`python -m compileall app tests` -> exit 0；`python -m pytest tests/test_frontend_v06_chat.py tests/test_frontend_v07_chat_experience.py tests/test_frontend_v071_command_palette.py -q` -> 9 passed；`npm --prefix frontend run build` -> passed with existing Vite large chunk warning；Browser smoke `http://localhost:8000/#/chat` 确认品牌、设置入口和身份区移除。

### 2026-06-10 | TASK-063 | 召回质量端到端验收和 WeKnora 链路文档
- summary: 将 TASK-056 法律召回夹具从 xfail 暴露用例升级为通过型验收：交通事故复杂问答必须把机动车交通事故、交强险、商业三者险相关条文选为最终 top context，不再把饲养动物致害作为首个 selected context；新增 Quick Q&A WeKnora 对齐召回链路文档，说明上线链路的 query understand、over-retrieval、hybrid/RRF、low-recall query expansion、mandatory composite rerank/MMR、chunk merge/context select、answer/sources 和 trace 排障方式；同步 README 与 v0.9 文档中的当前链路和参数口径。
- files: `tests/test_task056_legal_retrieval_fixture.py`, `docs/quick-answer-weknora-aligned-chain-2026-06-10.zh-CN.md`, `README.md`, `docs/v0.9.md`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_task056_legal_retrieval_fixture.py -q` -> 2 passed; `python -m pytest tests/test_task056_legal_retrieval_fixture.py tests/test_document_processing_chunk_payload.py tests/test_v03_retriever.py tests/test_v03_knowledge_search.py tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_v09_hybrid_entry.py tests/test_v09_fixed_retrieval_config.py tests/test_v071_observability_status.py -q` -> 59 passed; `ruff check app tests` -> All checks passed; `python -m pytest -q` -> 218 passed; `python -m compileall app tests` -> exit 0.
- follow_ups: TASK-056 到 TASK-063 已完成；后续召回异常优先按 `docs/quick-answer-weknora-aligned-chain-2026-06-10.zh-CN.md` 的 trace checklist 排查模型配置、候选池、query expansion、rerank composite/MMR 和 context merge。

### 2026-06-10 | TASK-062 | 摄入侧 search_text 和 generated questions 增强
- summary: 为文档处理阶段预留可注入 `generated_question_generator`，默认关闭且不调用真实模型；测试可注入 fake generator 为 embedding chunks 生成 `metadata.generated_questions`，并同步到 chunk `search_text`、BM25 upsert chunks 和 Qdrant payload metadata/search_text。`search_text` 构造继续保留 title、context_header、content，并追加 generated questions；手工 generated question API 与推荐问题复用既有 metadata 契约。
- files: `app/services/document_processing.py`, `tests/test_document_processing_chunk_payload.py`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_document_processing_chunk_payload.py::test_document_processing_syncs_generated_questions_to_search_text_and_payload -q` -> 1 passed after first observing missing generator support; `python -m pytest tests/test_document_processing_chunk_payload.py tests/test_v08_chunks_api.py tests/test_v07_chat_experience.py tests/test_v03_knowledge_search.py -q` -> 20 passed; `python -m pytest tests/test_task056_legal_retrieval_fixture.py tests/test_document_processing_chunk_payload.py tests/test_v08_chunks_api.py tests/test_v03_retriever.py tests/test_v03_knowledge_search.py tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_v09_hybrid_entry.py tests/test_v09_fixed_retrieval_config.py tests/test_v071_observability_status.py -q -rxX` -> 61 passed, 1 xfailed; `ruff check app/services/document_processing.py app/services/knowledge_search.py app/rag/retriever/__init__.py app/rag/query_rewrite.py app/api/v1/quick_answer.py tests/test_document_processing_chunk_payload.py tests/test_v03_knowledge_search.py tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_v071_observability_status.py tests/test_task056_legal_retrieval_fixture.py` -> All checks passed; `python -m compileall app/services/document_processing.py app/services/knowledge_search.py app/rag/retriever/__init__.py app/rag/query_rewrite.py app/api/v1/quick_answer.py tests/test_document_processing_chunk_payload.py tests/test_v03_knowledge_search.py tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_v071_observability_status.py tests/test_task056_legal_retrieval_fixture.py` -> exit 0.
- follow_ups: 自动进入 `TASK-063`，做召回质量验收和 WeKnora 对齐链路文档。

### 2026-06-10 | TASK-061 | Low-recall Query Expansion
- summary: 对齐 WeKnora 本地 query expansion：当初始检索命中低于阈值时，基于 query 生成最多 5 个本地 variants（停用词过滤、关键短语、空格短语、分隔片段、疑问前缀清理），用降低后的 keyword threshold 追加候选；扩展命中会去重、过滤 parent chunk、进入 deduplicate/FAQ/rerank/parent/context 统一主链路，并优先保留主 hybrid 命中的 source identity；diagnostics 新增 `query_expansion` 阶段，记录 variants、lowered threshold、before/after count 和 added_hit_count。
- files: `app/services/knowledge_search.py`, `tests/test_v03_knowledge_search.py`, `tests/test_v071_observability_status.py`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_v03_knowledge_search.py::test_knowledge_search_expands_low_recall_query_with_keyword_variants -q` -> 1 passed after first observing missing `query_expansion` stage; `python -m pytest tests/test_v03_knowledge_search.py::test_knowledge_search_normalizes_keyword_only_to_hybrid_and_returns_method_scores tests/test_v03_knowledge_search.py::test_quick_answer_uses_hybrid_pipeline_and_keeps_source_metadata tests/test_quick_answer.py::test_quick_answer_uses_parent_context_and_records_final_trace_contract tests/test_v03_knowledge_search.py::test_knowledge_search_expands_low_recall_query_with_keyword_variants -q` -> 4 passed after fixing expansion source override regression; `python -m pytest tests/test_task056_legal_retrieval_fixture.py tests/test_v03_retriever.py tests/test_v03_knowledge_search.py tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_v09_hybrid_entry.py tests/test_v09_fixed_retrieval_config.py tests/test_v071_observability_status.py -q -rxX` -> 53 passed, 1 xfailed; `ruff check app/services/knowledge_search.py tests/test_v03_knowledge_search.py tests/test_v071_observability_status.py` -> All checks passed; `python -m compileall app/services/knowledge_search.py tests/test_v03_knowledge_search.py tests/test_v071_observability_status.py` -> exit 0.
- follow_ups: 自动进入 `TASK-062`，增强 ingestion search_text/generated questions 契约。

### 2026-06-10 | TASK-060 | CHUNK_MERGE 等价上下文组装
- summary: 在现有 `ParentChildExpander` 上补齐 WeKnora `CHUNK_MERGE` 的关键上下文能力：child 命中继续解析 parent context，短 `text` 命中会按 `pre_chunk_id/next_chunk_id` 拉取同文档前后邻居组成 prompt context；source 仍保留原命中的 chunk identity 和 content，`context_content`/rendered context/answer 使用合并后的上下文；metadata 记录 neighbor merge chunk ids。当前实现覆盖 knowmate v1 主路径的 parent-child 与短文本邻居扩展，复杂 start/end range overlap 合并留待 RetrievalHit 扩展 range 契约后继续深化。
- files: `app/rag/retriever/__init__.py`, `tests/test_quick_answer.py`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_quick_answer.py::test_quick_answer_merges_short_hit_with_neighbor_chunks -q` -> 1 passed after first observing the expected red failure where `context_content` was `None`; `python -m pytest tests/test_v03_retriever.py tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_task056_legal_retrieval_fixture.py -q -rxX` -> 36 passed, 1 xfailed; `python -m pytest tests/test_task056_legal_retrieval_fixture.py tests/test_v03_retriever.py tests/test_v03_knowledge_search.py tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_v09_hybrid_entry.py tests/test_v09_fixed_retrieval_config.py tests/test_v071_observability_status.py -q -rxX` -> 52 passed, 1 xfailed; `ruff check app/rag/retriever/__init__.py tests/test_quick_answer.py` -> All checks passed; `python -m compileall app/rag/retriever/__init__.py tests/test_quick_answer.py` -> exit 0.
- follow_ups: 自动进入 `TASK-061`，实现低召回时的本地 query expansion。

### 2026-06-10 | TASK-059 | Rerank enriched passage、composite score 和 MMR 对齐
- summary: 将 `RerankPipeline` 对齐 WeKnora rerank 关键策略：rerank passage 由 `context_header`、context/content、`metadata.generated_questions` 和图片 OCR/Caption 文本组成并统一清洗；rerank 结果不再用模型分直接覆盖排序，而是使用 `0.6 * rerank_score + 0.3 * base_score + 0.1 * source_weight` 的 composite score；MMR 使用 enriched passage token set 去冗余；rerank diagnostics 输出 `score_details`，包含 chunk、base_score、rerank_score、composite_score 以及既有 mmr input/output。
- files: `app/rag/retriever/__init__.py`, `tests/test_v03_retriever.py`, `tests/test_quick_answer.py`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_v03_retriever.py::test_rerank_pipeline_sends_enriched_passages_to_model tests/test_v03_retriever.py::test_rerank_pipeline_uses_composite_score_instead_of_model_score_only -q` -> 2 passed after first observing expected red failures; `python -m pytest tests/test_v03_retriever.py -q` -> 16 passed; `python -m pytest tests/test_task056_legal_retrieval_fixture.py tests/test_v03_retriever.py tests/test_v03_knowledge_search.py tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_v09_hybrid_entry.py tests/test_v09_fixed_retrieval_config.py tests/test_v071_observability_status.py -q -rxX` -> 51 passed, 1 xfailed; `ruff check app/rag/retriever/__init__.py app/services/knowledge_search.py tests/test_v03_retriever.py tests/test_quick_answer.py` -> All checks passed; `python -m compileall app/rag/retriever/__init__.py app/services/knowledge_search.py tests/test_v03_retriever.py tests/test_quick_answer.py` -> exit 0.
- follow_ups: 自动进入 `TASK-060`，实现 WeKnora-style `CHUNK_MERGE` 等价上下文组装。

### 2026-06-10 | TASK-058 | WeKnora-style Over-retrieval 和候选池放大
- summary: 对齐 WeKnora `HybridSearch` 的 over-retrieval 思路，在 knowledge search 内部新增 `over_retrieval_limit = min(max(rerank_top_k * 5, 50) * scope_count, 500)`；raw vector/keyword 和 RRF 候选池使用该 limit，不再在 RRF 阶段固定截断到 30；diagnostics 记录 `over_retrieval_limit`、configured limit、实际 vector/keyword/RRF count 和 rerank input count，同时保持公开 retrieval config 仍为 v0.9 固定主链路，不重新暴露 retrieval mode。
- files: `app/services/knowledge_search.py`, `tests/test_v03_knowledge_search.py`, `tests/test_v09_hybrid_entry.py`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_v03_knowledge_search.py::test_knowledge_search_keeps_weknora_style_over_retrieval_pool -q` -> 1 passed after first observing the expected red failure where RRF output was 30; `python -m pytest tests/test_v09_fixed_retrieval_config.py tests/test_v09_hybrid_entry.py tests/test_v03_knowledge_search.py tests/test_v06_quick_answer_stream.py -q` -> 21 passed; `python -m pytest tests/test_task056_legal_retrieval_fixture.py tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_v071_observability_status.py tests/test_v03_knowledge_search.py tests/test_v09_hybrid_entry.py tests/test_v09_fixed_retrieval_config.py -q -rxX` -> 35 passed, 1 xfailed; `ruff check app/services/knowledge_search.py tests/test_v03_knowledge_search.py tests/test_v09_hybrid_entry.py` -> All checks passed; `python -m compileall app/services/knowledge_search.py tests/test_v03_knowledge_search.py tests/test_v09_hybrid_entry.py` -> exit 0.
- follow_ups: 自动进入 `TASK-059`，补 rerank enriched passage、composite score 和 MMR，解决候选池内错误主题误排。

### 2026-06-10 | TASK-057 | WeKnora-style Query Understand
- summary: 将 Quick Q&A 的 history-only query rewrite 改为 WeKnora-style `QUERY_UNDERSTAND`：无历史也会调用结构化 query understand prompt，要求输出 `rewrite_query/intent/image_description` JSON，保留实体和核心检索词并禁止“请在知识库中查找”类元指令；解析结果进入 `query_normalized/query_rewritten/query_intent` trace，非结构化输出标记失败并降级原 query；流式 `rewrite` SSE 事件改为展示实际 rewrite 状态和 intent。
- files: `app/rag/query_rewrite.py`, `app/services/quick_answer.py`, `app/api/v1/quick_answer.py`, `tests/conftest.py`, `tests/test_quick_answer.py`, `tests/test_v06_quick_answer_stream.py`, `tests/test_v071_observability_status.py`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_quick_answer.py::test_quick_answer_runs_query_understand_without_history -q` -> 1 passed after first observing the expected red failure; `python -m pytest tests/test_v06_quick_answer_stream.py::test_quick_answer_stream_creates_session_messages_and_final_sources -q` -> 1 passed after first observing the expected SSE payload failure; `python -m pytest tests/test_task056_legal_retrieval_fixture.py tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_v071_observability_status.py tests/test_v03_knowledge_search.py -q -rxX` -> 28 passed, 1 xfailed; `ruff check app/rag/query_rewrite.py app/services/quick_answer.py app/api/v1/quick_answer.py tests/conftest.py tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_v071_observability_status.py` -> All checks passed; `python -m compileall app/rag/query_rewrite.py app/services/quick_answer.py app/api/v1/quick_answer.py tests/conftest.py tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_v071_observability_status.py tests/test_task056_legal_retrieval_fixture.py` -> exit 0.
- follow_ups: 自动进入 `TASK-058`，对齐 WeKnora over-retrieval 候选池放大，避免 RRF 过早裁剪相关条文。

### 2026-06-10 | TASK-056 | Quick Q&A 召回退化复现和评测夹具
- summary: 新增交通事故法律问答召回退化夹具，固定“机动车交通事故/交强险/商业三者险”目标条文与“饲养动物/高度危险动物”干扰条文；测试使用 fake embedding/vector/rerank/chat client 构造可重复 Quick Q&A 请求，报告 query、vector candidates、vector/keyword/RRF/rerank/context_select 阶段计数、selected_contexts 和关键词命中状态；同时新增一个 xfail 质量门槛，记录当前首个最终上下文仍可能被错误主题占据，供 TASK-057 到 TASK-063 逐步修复。
- files: `tests/test_task056_legal_retrieval_fixture.py`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_task056_legal_retrieval_fixture.py -q -rxX` -> 1 passed, 1 xfailed; `ruff check tests/test_task056_legal_retrieval_fixture.py` -> All checks passed; `python -m compileall tests/test_task056_legal_retrieval_fixture.py` -> exit 0; `python -m pytest tests/test_quick_answer.py tests/test_v03_knowledge_search.py tests/test_task056_legal_retrieval_fixture.py -q -rxX` -> 18 passed, 1 xfailed.
- follow_ups: 自动进入 `TASK-057`，对齐 WeKnora `QUERY_UNDERSTAND`，让无历史复杂问题也先生成保留实体和检索关键词的结构化 query trace。

### 2026-06-08 | DOCS | v0.9 当前版本文档同步
- summary: 同步当前 v0.9 文档口径：KnowMate 固定 Quick Q&A 主链路已完成 TASK-046 到 TASK-055；默认开发运行方式为 Docker API + Docker worker + 本机 Vite；`scripts/start-dev.ps1` 负责启动 Docker 后端栈和本机 Vite，不等同于自动化测试；不要混跑本机 `uvicorn` / `celery` 与 Docker `api` / `worker`。
- files: `README.md`, `CHANGELOG.md`, `docs/v0.9.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_dev_start_script.py tests/test_docker_compose_stack.py -q` -> 9 passed; `ruff check tests/test_dev_start_script.py tests/test_docker_compose_stack.py` -> All checks passed; `scripts/start-dev.ps1` -> Docker `api / worker / postgres / redis / qdrant` healthy, `/health` ok, frontend 5173 returned 200, Celery ping showed one Docker worker online.
- follow_ups: 更新项目代码后先运行 `scripts/start-dev.ps1` 启动环境；需要确认代码质量时继续运行 `python -m pytest -q`、`ruff check .`、`python -m compileall app tests` 和 `npm --prefix frontend run build`。

### 2026-06-03 | v0.8 | TASK-025 到 TASK-045 版本归档
- summary: 将 TASK-025 到 TASK-045 归档为 `v0.8`：retrieval diagnostics、trace 前端展示、rendered context、history merge、rerank cleaning/MMR、FAQ import progress、FAQ 字段批量更新、FAQ boost、chunk by-id/update/disable、generated questions、chunk 管理前端、chunk debug、token-aware validation、message search、model providers、vector-store types、composite retriever、OpenSearch sparse MVP、runtime status 真实化和文本附件上下文，共同构成 v0.71 操作闭环之后的 WeKnora-style Quick Q&A 可解释性、检索质量和管理闭环版本。
- files: `README.md`, `CHANGELOG.md`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`, `docs/weknora-full-gap-analysis-2026-06-02.zh-CN.md`
- verification: `python -m pytest -q` -> 184 passed; `ruff check app tests` -> All checks passed; `python -m compileall app tests alembic` -> exit 0; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning; startup smoke after `scripts/start-dev.ps1` -> `/health` ok, Alembic current `0016_task032_faq_recommended (head)`, frontend `/#/chat` showed backend connected.
- follow_ups: 后续任务从 v0.8 基线继续排队，优先考虑 Auth/RBAC-lite、per-user 偏好、文件夹上传、Web Search provider、Markdown/Mermaid 安全渲染、高级解析、Agent/Wiki/DataSource 等范围。

### 2026-06-03 | TASK-045 | Attachment Context MVP
- summary: 新增 Quick Q&A 临时文本附件上下文 MVP；请求支持 txt/md/csv/json 附件 payload，后端限制数量、64KB 大小、行数和字符数，构造 `<attachments>` prompt section；附件可在无知识库命中时驱动回答，但不写入长期知识库、不进入 Qdrant、不出现在 sources；retrieval_trace/rendered_context/last_request_state 记录 `attachments_used`、metadata 和截断状态；ChatMessage 保存附件 metadata；前端 Chat 输入支持选择临时附件、中文类型/大小错误和截断提示。
- files: `app/rag/attachments.py`, `app/rag/prompt.py`, `app/schemas/quick_answer.py`, `app/schemas/chat.py`, `app/services/quick_answer.py`, `app/services/chat.py`, `app/api/v1/quick_answer.py`, `frontend/src/types/api.ts`, `frontend/src/stores/chat.ts`, `frontend/src/views/ChatView.vue`, `tests/test_quick_answer.py`, `tests/test_v06_quick_answer_stream.py`, `tests/test_frontend_v06_chat.py`, `frontend/dist/**`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_quick_answer.py::test_quick_answer_uses_text_attachment_context_without_sources tests/test_quick_answer.py::test_quick_answer_rejects_oversized_attachment_with_chinese_error tests/test_v06_quick_answer_stream.py::test_quick_answer_stream_saves_attachment_metadata_and_truncation tests/test_frontend_v06_chat.py::test_frontend_chat_supports_text_attachments -q` -> 4 passed; `python -m pytest tests/test_v06_chat_sessions.py tests/test_v06_quick_answer_stream.py tests/test_frontend_v06_chat.py -q` -> 15 passed; `python -m pytest tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_v06_chat_sessions.py tests/test_frontend_v06_chat.py -q` -> 24 passed; `python -m pytest -q` -> 184 passed; `python -m compileall app tests alembic` -> exit 0; `ruff check app tests` -> All checks passed; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning.
- follow_ups: TASK-025 到 TASK-045 已全部完成并通过全量验收。

### 2026-06-03 | TASK-044 | Runtime Status 真实化
- summary: 增强 `/api/v1/runtime-status`，返回 database/local storage/vector runtime 的延迟与检查时间、`model_configs` 必需模型状态摘要、`vector_stores` 安全配置摘要、`storage_providers` local/planned 对象存储状态、parser engines 的 builtin/OCR/MinerU/DocReader 可用性和 `fix_suggestions`；前端 Settings 页面新增运行状态摘要，展示模型配置、VectorStore、对象存储 planned 状态和修复建议。
- files: `app/api/v1/runtime_status.py`, `frontend/src/types/api.ts`, `frontend/src/views/SettingsView.vue`, `tests/test_v071_observability_status.py`, `tests/test_frontend_v071_observability_status.py`, `frontend/dist/**`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_v071_observability_status.py::test_runtime_status_reports_real_parser_storage_and_system_health tests/test_frontend_v071_observability_status.py::test_frontend_loads_runtime_status_and_shows_stage_trace -q` -> 2 passed; `python -m pytest tests/test_v071_observability_status.py tests/test_frontend_v071_observability_status.py -q` -> 3 passed; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning; `python -m compileall app tests alembic` -> exit 0; `ruff check app tests` -> All checks passed.
- follow_ups: 自动进入 `TASK-045`。

### 2026-06-03 | TASK-043 | OpenSearch/Elasticsearch Sparse/BM25 后端 MVP
- summary: 新增 `OpenSearchSparseStore` MVP，提供 fake/test-client 可用的 sparse/BM25-style 索引、搜索、启停、标签、payload、移动和删除接口；`VectorStoreRegistry` 支持通过 fake/test client 构建 OpenSearch/Elasticsearch sparse store，未配置时返回中文明确错误；VectorStore API 仍禁止非 Qdrant 创建且不回显 secret；检索 diagnostics 的 retriever fan-out 明确标出默认 `vector_engine=qdrant`、`keyword_engine=postgres`，确保现有 Qdrant/PostgreSQL 路径不回退。
- files: `app/integrations/opensearch_store.py`, `app/integrations/vector_store.py`, `app/services/knowledge_search.py`, `tests/test_v03_retriever.py`, `tests/test_v05_vector_stores.py`, `tests/test_v03_knowledge_search.py`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_v03_retriever.py::test_opensearch_sparse_store_fake_indexes_searches_and_syncs_payload_state tests/test_v03_retriever.py::test_opensearch_sparse_store_requires_configuration_without_fake_client tests/test_v05_vector_stores.py::test_vector_store_registry_builds_fake_opensearch_sparse_store tests/test_v05_vector_stores.py::test_vector_store_registry_rejects_unconfigured_opensearch_provider tests/test_v03_knowledge_search.py::test_knowledge_search_returns_hybrid_retrieval_diagnostics -q` -> 5 passed; `python -m pytest tests/test_v05_vector_stores.py tests/test_v03_retriever.py tests/test_v03_knowledge_search.py -q` -> 28 passed; `python -m compileall app tests alembic` -> exit 0; `ruff check app tests` -> All checks passed.
- follow_ups: 自动进入 `TASK-044`。

### 2026-06-03 | TASK-042 | Composite Retriever 接口
- summary: 在 KnowledgeSearchService 中引入 `CompositeKnowledgeRetriever` 包装 per-KB 检索，保留当前 Qdrant vector + PostgreSQL keyword + RRF 行为；diagnostics 新增 `retrievers` fan-out 列表，按 KB 记录 knowledge_base_id/name、engine、mode、status、hit_count、duration_ms 和错误信息；现有 vector/keyword/rrf/parent/deduplicate/faq/rerank stages 与 source shape 保持兼容。
- files: `app/services/knowledge_search.py`, `tests/test_v07_multi_scope_retrieval.py`, `tests/test_v03_knowledge_search.py`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_v07_multi_scope_retrieval.py tests/test_v03_knowledge_search.py -q` -> 12 passed; `python -m pytest tests/test_v07_multi_scope_retrieval.py tests/test_v03_knowledge_search.py tests/test_quick_answer.py -q` -> 19 passed; `python -m compileall app tests alembic` -> exit 0; `ruff check app tests` -> All checks passed.
- follow_ups: 自动进入 `TASK-043`。

### 2026-06-03 | TASK-041 | Vector Store Types 和可用性状态
- summary: 新增 `/api/v1/vector-stores/types`，返回 Qdrant available 以及 OpenSearch、Elasticsearch、Milvus、Weaviate、Doris、Tencent VectorDB planned 的 provider metadata；每个 type 包含 connection_fields、index_fields、sensitive 和 default 信息；非 Qdrant 创建会返回中文明确错误并标明 provider 状态，且不回显 secret；前端 vector store 设置页加载 types API 并展示 provider 可用性、连接字段和索引字段。
- files: `app/api/v1/vector_stores.py`, `app/schemas/vector_store.py`, `app/services/vector_store.py`, `frontend/src/types/api.ts`, `frontend/src/stores/vectorStores.ts`, `frontend/src/views/VectorStoreSettingsView.vue`, `tests/test_v05_vector_stores.py`, `tests/test_frontend_v03_retrieval.py`, `frontend/dist/**`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_v05_vector_stores.py -q` -> 5 passed; `python -m pytest tests/test_frontend_v03_retrieval.py -q` -> 2 passed; `python -m pytest tests/test_v05_vector_stores.py tests/test_frontend_v03_retrieval.py -q` -> 7 passed; `python -m compileall app tests alembic` -> exit 0; `ruff check app tests` -> All checks passed; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning.
- follow_ups: 自动进入 `TASK-042`。

### 2026-06-03 | TASK-040 | Model Providers 和模型分组
- summary: 新增 `/api/v1/models/providers`，返回稳定的 OpenAI-compatible provider presets（Qwen/DashScope、DeepSeek、OpenAI 兼容），包含支持的模型类型、默认 Base URL、默认模型名、embedding dimension 和敏感 credential field 标记；前端模型 store 加载 providerPresets，模型表单优先从后端 preset 填充 base_url/model_name/embedding_dimension，模型列表按 KnowledgeQA、Embedding、Rerank 模型组展示；API Key 仍只返回 configured/last4，不回显明文。
- files: `app/api/v1/models.py`, `app/schemas/models.py`, `app/services/model_config.py`, `frontend/src/types/api.ts`, `frontend/src/stores/models.ts`, `frontend/src/components/ModelConfigForm.vue`, `frontend/src/views/ModelSettingsView.vue`, `tests/test_model_config.py`, `tests/test_frontend_v02_model_management.py`, `frontend/dist/**`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_model_config.py -q` -> 5 passed; `python -m pytest tests/test_frontend_v02_model_management.py -q` -> 5 passed; `python -m pytest tests/test_model_config.py tests/test_v02_model_binding_reprocess.py tests/test_frontend_v02_model_management.py -q` -> 16 passed; `python -m compileall app tests alembic` -> exit 0; `ruff check app tests` -> All checks passed; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning. Browser check hit the current hash route and backend remained unhealthy, but frontend shell rendered.
- follow_ups: 自动进入 `TASK-041`。

### 2026-06-03 | TASK-039 | Message Search 和 Chat History Stats
- summary: 新增 WeKnora-style `/api/v1/messages/search` 与 `/api/v1/messages/chat-history-stats`；message search 使用关键词 ILIKE 检索当前租户未删除会话中的消息，并把命中的 user/assistant 消息配对成 Q/A 结果，返回 session title、query、answer、answer_snippet、created_at 和 match_type；stats 返回 session_count、message_count、last_message_at、searchable 以及兼容的 indexed fields；Chat 侧栏新增“历史问答搜索”和可检索消息数，结果可点击打开会话；Command Palette 增加“历史问答搜索”入口。
- files: `app/api/v1/messages.py`, `app/api/v1/router.py`, `app/db/repositories/chat.py`, `app/schemas/chat.py`, `app/services/chat.py`, `frontend/src/types/api.ts`, `frontend/src/stores/chat.ts`, `frontend/src/views/ChatView.vue`, `frontend/src/components/CommandPalette.vue`, `tests/test_v06_chat_sessions.py`, `tests/test_frontend_v07_chat_experience.py`, `tests/test_frontend_v071_command_palette.py`, `frontend/dist/**`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_v06_chat_sessions.py -q` -> 4 passed; `python -m pytest tests/test_frontend_v07_chat_experience.py tests/test_frontend_v071_command_palette.py -q` -> 3 passed; `python -m pytest tests/test_v06_chat_sessions.py tests/test_v07_chat_experience.py tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_frontend_v07_chat_experience.py tests/test_frontend_v071_command_palette.py -q` -> 23 passed; `python -m compileall app tests alembic` -> exit 0; `ruff check app tests` -> All checks passed; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning. Browser opened `http://127.0.0.1:5173/chat`; frontend shell rendered, backend was not running/healthy so it showed “后端未连接” and `/health` returned 500.
- follow_ups: 自动进入 `TASK-040`。

### 2026-06-03 | TASK-038 | Token-aware Chunking Validation
- summary: 增加 WeKnora-style 轻量 token 估算，按 en/de/zh/mixed chars-per-token 预算处理 `token_limit`，并在 chunker diagnostics 中记录 `token_limit_applied`、生效原因、请求/生效 chunk size 和 fallback tier；preview API 返回 token stats（avg/min/max/stddev/token_limit）并用同一估算计算每个 chunk 的 approx tokens；前端 debug 面板展示 Token 上限、生效 chunk size、平均/最大 tokens 和 token_limit 生效原因；新增中英文/混合语言、长英文单词、密集中文、表格和代码块保护测试。
- files: `app/rag/chunker.py`, `app/api/v1/chunker.py`, `app/schemas/chunker.py`, `frontend/src/components/ChunkPreview.vue`, `frontend/src/types/api.ts`, `tests/test_chunker.py`, `tests/test_chunker_preview_api.py`, `tests/test_frontend_chunking_settings.py`, `frontend/dist/**`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_chunker.py tests/test_chunker_preview_api.py -q` -> 9 passed; `python -m pytest tests/test_frontend_chunking_settings.py -q` -> 3 passed; `python -m pytest tests/test_chunker.py tests/test_chunker_preview_api.py tests/test_frontend_chunking_settings.py -q` -> 12 passed; `python -m compileall app tests alembic` -> exit 0; `ruff check app tests` -> All checks passed; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning.
- follow_ups: 自动进入 `TASK-039`。

### 2026-06-03 | TASK-037 | Chunk Debug UI 增强
- summary: 增强 chunker preview/debug 诊断输出和前端展示；preview API 新增 `protected_blocks` 与 `stats.size_distribution`，保留 selected tier、tier chain、rejected tiers、profile 和 chunk card 元数据；前端 `ChunkPreview` 展示策略链、被拒绝层级/拒绝原因、文档画像、保护块统计、Chunk 分布，以及每个 chunk 的 `start/end`、`approx tokens`、`context_header` 和正文预览；预览失败转成中文提示。
- files: `app/rag/chunker.py`, `app/api/v1/chunker.py`, `app/schemas/chunker.py`, `frontend/src/components/ChunkPreview.vue`, `frontend/src/types/api.ts`, `tests/test_chunker_preview_api.py`, `tests/test_frontend_chunking_settings.py`, `frontend/dist/**`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_chunker_preview_api.py tests/test_chunker.py -q` -> 6 passed; `python -m pytest tests/test_frontend_chunking_settings.py -q` -> 2 passed; `python -m compileall app tests alembic` -> exit 0; `ruff check app tests` -> All checks passed; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning.
- follow_ups: 自动进入 `TASK-038`。

### 2026-06-03 | TASK-036 | Chunk 管理前端
- summary: 文档预览中的每个 chunk 增加“Chunk 详情”入口；新增 chunk detail drawer，支持编辑 content、search_text、metadata、启用状态，并在内容变化后用中文提示需要重建 embedding；支持新增和删除 generated questions，所有 API 错误经 `formatApiError` 转成中文/可读文本；前端 store/type 接入 chunk by-id、update 和 generated question API。
- files: `app/schemas/document.py`, `frontend/src/types/api.ts`, `frontend/src/stores/knowledgeBase.ts`, `frontend/src/utils/api.ts`, `frontend/src/views/DocumentsView.vue`, `tests/test_frontend_v08_chunk_management.py`, `frontend/dist/**`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_frontend_v08_chunk_management.py -q` -> 1 passed; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning; `python -m pytest tests/test_frontend_v07_document_preview.py tests/test_frontend_v08_chunk_management.py -q` -> 2 passed; `python -m pytest tests/test_v08_chunks_api.py tests/test_document_processing_chunk_payload.py -q` -> 4 passed; `python -m compileall app tests alembic` -> exit 0; `ruff check app tests` -> All checks passed. Browser opened `http://127.0.0.1:5173/knowledge-bases`; frontend rendered, but backend was not running so the page showed “后端未连接”.
- follow_ups: 自动进入 `TASK-037`。

### 2026-06-03 | TASK-035 | Generated Questions 后端和索引
- summary: Chunk metadata 支持 WeKnora-style `generated_questions` 列表 `{id, question}`；新增 `POST /api/v1/chunks/by-id/{chunk_id}/questions` 手动添加生成问题，`DELETE /api/v1/chunks/by-id/{chunk_id}/questions` 删除指定 question；添加/删除会同步 chunk `search_text` 与 vector payload metadata，使 keyword 检索和 source metadata 能使用 generated questions；推荐问题接口继续优先返回 chunk generated questions。
- files: `app/api/v1/chunks.py`, `app/schemas/chunk.py`, `app/services/chunk.py`, `tests/test_v08_chunks_api.py`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_v08_chunks_api.py::test_generated_questions_update_chunk_metadata_search_and_recommendations -q` -> 1 passed; `python -m pytest tests/test_v08_chunks_api.py tests/test_v07_chat_experience.py tests/test_v03_knowledge_search.py -q` -> 13 passed; `python -m pytest tests/test_document_processing_chunk_payload.py tests/test_quick_answer.py -q` -> 8 passed; `python -m compileall app tests alembic` -> exit 0; `ruff check app tests` -> All checks passed; `alembic heads` -> `0016_task032_faq_recommended_fields (head)`.
- follow_ups: 自动进入 `TASK-036`。

### 2026-06-03 | TASK-034 | Chunk by-id / Update / Disable 后端 API
- summary: 新增 WeKnora-style chunk 管理后端 API：`GET /api/v1/chunks/by-id/{chunk_id}` 查询单 chunk，`PUT /api/v1/chunks/{knowledge_id}/{chunk_id}` 更新 content/search_text/metadata/is_enabled，`DELETE /api/v1/chunks/{knowledge_id}/{chunk_id}` 软删除/禁用；更新后文档 chunks 列表返回新内容，内容或 search_text 变更返回 `requires_reindex=true`；启停同步 vector payload 的 `is_enabled`，禁用后 quick-answer 不再召回该 chunk。
- files: `app/api/v1/chunks.py`, `app/api/v1/router.py`, `app/db/repositories/chunk.py`, `app/schemas/chunk.py`, `app/services/chunk.py`, `app/integrations/qdrant_store.py`, `tests/conftest.py`, `tests/test_v08_chunks_api.py`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_v08_chunks_api.py -q` -> 2 passed; `python -m pytest tests/test_v08_chunks_api.py tests/test_document_processing_chunk_payload.py tests/test_v03_knowledge_search.py tests/test_quick_answer.py -q` -> 17 passed; `python -m pytest tests/test_v021_crud_endpoints.py tests/test_v071_document_lifecycle.py tests/test_v05_document_management.py -q` -> 13 passed; `python -m compileall app tests alembic` -> exit 0; `ruff check app tests` -> All checks passed; `alembic heads` -> `0016_task032_faq_recommended_fields (head)`.
- follow_ups: 自动进入 `TASK-035`。

### 2026-06-03 | TASK-033 | FAQ Merge / Boost 独立策略
- summary: 在检索 diagnostics 中新增 `faq_merge` 阶段，识别 FAQ chunk 并对高置信 FAQ 命中进行有限 score boost 和重新排序；boost 结果保留 `matched_question`、`standard_question`、`question_role` 等 metadata，并在 trace 记录输入数、输出数、FAQ 数、boost 数和最大 boost factor；低置信 FAQ 不会无条件压过文档；前端 trace 标签新增“FAQ 合并”并展示 Boost 数。
- files: `app/services/knowledge_search.py`, `frontend/src/views/ChatView.vue`, `tests/test_v03_knowledge_search.py`, `tests/test_v071_observability_status.py`, `tests/test_frontend_v06_chat.py`, `frontend/dist/**`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_v03_knowledge_search.py::test_knowledge_search_faq_merge_boosts_high_confidence_faq_and_traces_stage tests/test_v03_knowledge_search.py::test_knowledge_search_faq_merge_does_not_promote_low_confidence_faq -q` -> 2 passed; `python -m pytest tests/test_v03_knowledge_search.py tests/test_v07_faq_similar_indexing.py tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_v071_observability_status.py tests/test_frontend_v06_chat.py -q` -> 27 passed; `python -m compileall app tests alembic` -> exit 0; `ruff check app tests` -> All checks passed; `alembic heads` -> `0016_task032_faq_recommended_fields (head)`; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning.
- follow_ups: 自动进入 `TASK-034`。

### 2026-06-03 | TASK-032 | FAQ 字段批量更新
- summary: 新增 WeKnora-style FAQ fields batch update；FAQ 条目支持 `is_recommended` 字段，批量接口兼容 `enabled/is_enabled`、`recommended/is_recommended` 和 `tag_id`，逐条重建索引并返回中文部分失败摘要；FAQ tag/recommended 信息同步到 chunk 和 Qdrant payload；FAQ 管理页支持多选批量启用、停用、推荐、取消推荐和批量标签。
- files: `alembic/versions/0016_task032_faq_recommended_fields.py`, `app/db/models.py`, `app/db/repositories/chat.py`, `app/schemas/faq.py`, `app/services/faq.py`, `app/api/v1/faqs.py`, `app/integrations/qdrant_store.py`, `frontend/src/types/api.ts`, `frontend/src/stores/knowledgeBase.ts`, `frontend/src/views/FAQView.vue`, `tests/test_v05_faq.py`, `tests/test_frontend_v08_faq_batch_fields.py`, `frontend/dist/**`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_v05_faq.py::test_batch_updating_faq_fields_disables_search_and_reports_partial_failures tests/test_v05_faq.py::test_batch_updating_faq_tag_syncs_entry_chunks_and_vector_payload -q` -> 2 passed; `python -m pytest tests/test_frontend_v08_faq_batch_fields.py -q` -> 1 passed; `python -m pytest tests/test_v05_faq.py tests/test_v07_tags.py tests/test_v07_faq_similar_indexing.py tests/test_v07_faq_import_export.py tests/test_v07_chat_experience.py -q` -> 16 passed; `python -m pytest tests/test_frontend_v07_faq_import_export.py tests/test_frontend_v08_faq_batch_fields.py -q` -> 2 passed; `python -m compileall app tests alembic` -> exit 0; `ruff check app tests` -> All checks passed; `alembic heads` -> `0016_task032_faq_recommended_fields (head)`; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning.
- follow_ups: 自动进入 `TASK-033`。

### 2026-06-03 | TASK-031 | FAQ Import Progress 和 Last Result
- summary: 新增持久化 `faq_import_results` 表和 migration；FAQ 同步导入返回并保存 `task_id`、total、processed、succeeded/imported、failed、status、progress、failures、error_summary、display_status 和 processing_time；新增 import progress、last result、关闭显示状态 API；FAQ 管理页刷新后加载 last import result，支持关闭提示且保留历史结果 API 可查。
- files: `alembic/versions/0015_task031_faq_import_results.py`, `app/db/models.py`, `app/schemas/faq.py`, `app/services/faq_import_export.py`, `app/api/v1/faqs.py`, `frontend/src/types/api.ts`, `frontend/src/stores/knowledgeBase.ts`, `frontend/src/views/FAQView.vue`, `tests/test_v07_faq_import_export.py`, `tests/test_frontend_v07_faq_import_export.py`, `frontend/dist/**`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_v07_faq_import_export.py tests/test_v05_faq.py -q` -> 5 passed; `python -m pytest tests/test_frontend_v07_faq_import_export.py -q` -> 1 passed; `python -m compileall app tests alembic` -> exit 0; `ruff check app tests` -> All checks passed; `alembic heads` -> `0015_task031_faq_import_results (head)`; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning. Online `alembic upgrade head` was not rerun because PostgreSQL/Docker is unavailable in this environment, same blocker recorded in TASK-027.
- follow_ups: 自动进入 `TASK-032`。

### 2026-06-03 | TASK-030 | Rerank 阈值降级和 MMR 去冗余
- summary: `RerankPipeline` 支持高阈值空结果时降级阈值重试，并在仍无结果但 top1 可用时保留 top1 fallback；rerank 后应用轻量 MMR，降低重复 chunk 挤占上下文；rerank diagnostics 透传到 retrieval trace，包含 `original_threshold`、`degraded_threshold`、`top1_fallback`、`mmr_input_count`、`mmr_output_count`。
- files: `app/rag/retriever/__init__.py`, `app/services/knowledge_search.py`, `tests/test_v03_retriever.py`, `tests/test_quick_answer.py`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_v03_retriever.py tests/test_v03_knowledge_search.py -q` -> 17 passed; `python -m pytest tests/test_quick_answer.py -q` -> 7 passed; `python -m compileall app tests` -> exit 0; `ruff check app tests` -> All checks passed.
- follow_ups: 自动进入 `TASK-031`。

### 2026-06-03 | TASK-029 | Rerank Passage Cleaning 和失败降级
- summary: `clean_rerank_passage` 增强 markdown link、raw URL、table row、heading 和 code block 清理；rerank 已配置但 provider/API 调用失败时不再让 Quick Answer 失败，而是保留原始检索结果，并在 rerank diagnostics stage 标记 `failed`、`fallback=true` 和中文错误；缺少 Rerank 模型配置仍沿用中文错误。
- files: `app/rag/retriever/__init__.py`, `app/services/knowledge_search.py`, `tests/test_v03_retriever.py`, `tests/test_quick_answer.py`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_v03_retriever.py tests/test_v03_knowledge_search.py tests/test_quick_answer.py -q` -> 21 passed; `python -m compileall app tests` -> exit 0; `ruff check app tests` -> All checks passed.
- follow_ups: 自动进入 `TASK-030`。

### 2026-06-03 | TASK-028 | 多轮 History Merge
- summary: Quick Answer prompt 新增独立 `Conversation history` 区块，按最近 user/assistant 消息生成轻量 conversation context；trace 记录 `history_used`、`history_message_count`、`history_char_count`、`history_truncated`；query rewrite 失败时仍继续合并 history；超长历史采用“最新消息优先”的截断策略，避免丢掉当前追问前的最近上下文。
- files: `app/rag/prompt.py`, `app/services/quick_answer.py`, `tests/test_v06_quick_answer_stream.py`, `tests/test_quick_answer.py`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_v06_chat_sessions.py tests/test_v06_quick_answer_stream.py -q` -> 8 passed; `python -m pytest tests/test_quick_answer.py -q` -> 5 passed; `python -m compileall app tests` -> exit 0; `ruff check app tests` -> All checks passed.
- follow_ups: 自动进入 `TASK-029`。

### 2026-06-03 | TASK-027 | Rendered Context 持久化
- summary: 新增 `chat_messages.rendered_context` 和 `prompt_context_summary` migration/model/schema；Quick Answer 生成本次送入模型的检索上下文截断版和摘要，并在 retrieval_trace 记录 `context_chunk_ids`、`context_char_count`、`context_truncated`、`prompt_context_summary`；流式 assistant message 持久化 context summary，前端 trace 面板展示“本次送入模型的上下文摘要”。
- files: `alembic/versions/0014_task027_rendered_context.py`, `app/db/models.py`, `app/schemas/chat.py`, `app/services/chat.py`, `app/services/quick_answer.py`, `app/api/v1/quick_answer.py`, `frontend/src/types/api.ts`, `frontend/src/views/ChatView.vue`, `tests/test_quick_answer.py`, `tests/test_v06_quick_answer_stream.py`, `tests/test_frontend_v06_chat.py`, `frontend/dist/**`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_v06_chat_sessions.py tests/test_v06_quick_answer_stream.py -q` -> 7 passed; `python -m pytest tests/test_frontend_v06_chat.py -q` -> 3 passed; `python -m compileall app tests` -> exit 0; `ruff check app tests` -> All checks passed; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning; `alembic heads` -> `0014_task027_rendered_context (head)`; `python -m compileall alembic` -> exit 0. Online `alembic upgrade head` timed out because PostgreSQL/Docker was unavailable in this environment, and offline SQL generation is blocked by an older online data-migration step in `0004_v02_model_management.py`.
- follow_ups: 自动进入 `TASK-028`。

### 2026-06-03 | TASK-026 | Retrieval Trace 前端可解释展示
- summary: Chat 消息 trace 和知识检索调试面板展示 TASK-025 的阶段化 diagnostics；新增中文阶段名、状态文案、状态颜色和安全摘要格式化，覆盖 rewrite、vector、keyword、rrf、parent_expand、deduplicate、rerank、answer，并把 SourceCard 检索方法标签中文化。
- files: `frontend/src/views/ChatView.vue`, `frontend/src/components/SourceCard.vue`, `frontend/src/types/api.ts`, `frontend/src/stores/chat.ts`, `tests/test_frontend_v06_chat.py`, `frontend/dist/**`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_frontend_v06_chat.py tests/test_frontend_v071_observability_status.py -q` -> 3 passed; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning. Browser plugin attempted `http://127.0.0.1:5173/chat` but local URL navigation was blocked with `ERR_BLOCKED_BY_CLIENT`.
- follow_ups: 自动进入 `TASK-027`。

### 2026-06-03 | TASK-025 | Retrieval Diagnostics 后端基础
- summary: 为 `KnowledgeSearchService` 增加 `search_with_diagnostics`，按 vector、keyword、rrf、parent_expand、deduplicate、rerank 阶段输出 WeKnora-style diagnostics；`knowledge-search` 返回 hits + diagnostics；非流式和流式 Quick Answer 的 `retrieval_trace.stages` 复用检索 diagnostics，并在无命中时以中文错误标记 answer skipped。
- files: `app/services/knowledge_search.py`, `app/services/quick_answer.py`, `app/api/v1/knowledge_search.py`, `app/api/v1/quick_answer.py`, `app/schemas/knowledge_search.py`, `app/schemas/quick_answer.py`, `tests/test_v03_knowledge_search.py`, `tests/test_quick_answer.py`, `tests/test_v06_quick_answer_stream.py`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_quick_answer.py tests/test_v03_knowledge_search.py -q` -> 8 passed; `python -m pytest tests/test_v06_quick_answer_stream.py -q` -> 5 passed; `python -m compileall app tests` -> exit 0; `ruff check app tests` -> All checks passed.
- follow_ups: 自动进入 `TASK-026`。

### 2026-06-02 | DOCS | v0.71 当前版本文档归档
- summary: 将 README、CHANGELOG、AI Task Board 和 WeKnora 差距文档更新为当前 v0.71：归档 TASK-020 到 TASK-024，补充 v0.71 Schema/API 变化、运行状态、Command Palette、文档生命周期和重复上传修复说明，并补齐缺失的 `docs/weknora-local-comparison-v0.71-roadmap.zh-CN.md`。
- files: `README.md`, `CHANGELOG.md`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`, `docs/weknora-local-comparison-v0.71-roadmap.zh-CN.md`, `docs/weknora-local-comparison-v0.7-roadmap.zh-CN.md`, `docs/weknora-visible-gap-analysis-v0.6-v0.7.zh-CN.md`, `docs/weknora-visible-gap-analysis-v0.6-v0.7.md`
- verification: 文档版本文本搜索和 v0.71 关键 API/bugfix 文本一致性检查通过。
- follow_ups: v0.71 P1/P2 和 v0.72 候选继续保留在 `requirements.md` Parking Lot。

### 2026-06-02 | BUGFIX | 软删除后同文件重新上传
- summary: 修复同一文件首次上传后中止、软删除记录，再次上传时复用 deterministic document id 导致 `knowledges.id` 主键冲突并返回 Internal Server Error 的问题；现在活跃重复文件返回中文 409，已软删除同 hash 文件会生成新的 document id 并允许重新上传。
- files: `app/api/v1/documents.py`, `app/db/repositories/document.py`, `app/services/document.py`, `tests/test_v05_document_management.py`
- verification: `python -m pytest tests/test_v05_document_management.py::test_deleted_duplicate_file_can_be_uploaded_again tests/test_v05_document_management.py::test_active_duplicate_file_upload_returns_chinese_error -q` -> 2 passed; `python -m pytest tests/test_v05_document_management.py tests/test_v021_crud_endpoints.py tests/test_v071_document_lifecycle.py -q` -> 13 passed; `ruff check app\api\v1\documents.py app\db\repositories\document.py app\services\document.py tests\test_v05_document_management.py` -> passed; `python -m compileall app tests` -> passed.
- follow_ups: 无。

### 2026-06-02 | DOCS | v0.71 差距文档和任务规划
- summary: 重新对照 `D:/myproject/_references/WeKnora` 本地 `VERSION=0.6.0`、commit `e352721` 和迁移 `000057_models_display_name`，新增 v0.71 规划文档；把 v0.71 P0 收敛为上传队列、文档下载/取消/移动、停止生成/自动标题/last-request state、阶段化 retrieval trace + 真实 status API、Command Palette。
- files: `docs/weknora-local-comparison-v0.71-roadmap.zh-CN.md`, `docs/weknora-local-comparison-v0.7-roadmap.zh-CN.md`, `docs/weknora-visible-gap-analysis-v0.6-v0.7.zh-CN.md`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- follow_ups: 从 `TASK-020` 开始进入 v0.71；生产代码变更前仍按任务看板规则等待用户确认。

### 2026-06-02 | TASK-020 | 上传队列和多文件进度
- summary: 文档上传组件支持一次选择多个文件；文档页新增本地上传队列，逐文件展示 pending / uploading / queued / processing / completed / failed 状态，上传成功后展示 document id 和匹配到的 task id，并区分上传失败、解析失败和部分成功摘要。
- files: `frontend/src/components/DocumentUpload.vue`, `frontend/src/views/DocumentsView.vue`, `frontend/src/styles/app.css`, `tests/test_frontend_v071_upload_queue.py`, `frontend/dist/**`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- verification: `python -m pytest tests/test_frontend_v071_upload_queue.py -q` -> 1 passed; `python -m pytest tests/test_frontend_v071_upload_queue.py tests/test_frontend_file_picker.py tests/test_frontend_v07_batch_progress.py -q` -> 3 passed; `python -m pytest (rg --files tests | rg 'test_frontend_.*\\.py$') -q` -> 25 passed; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning.
- follow_ups: 自动进入 `TASK-021`。

### 2026-06-02 | TASK-021 | 文档下载、取消解析和移动到其他 KB
- summary: 增加文档原文件下载、queued/processing 取消解析、文档移动到兼容知识库的后端 API 和前端操作；取消会同步任务状态与处理 timeline 为 cancelled；移动会校验 KB 类型和 Embedding 模型兼容，并同步 chunk 与 Qdrant payload 的知识库归属。
- files: `app/api/v1/documents.py`, `app/db/repositories/document.py`, `app/db/repositories/task.py`, `app/integrations/qdrant_store.py`, `app/schemas/document.py`, `app/services/document.py`, `app/services/document_processing.py`, `app/services/processing_spans.py`, `app/services/task.py`, `app/workers/tasks.py`, `frontend/src/types/api.ts`, `frontend/src/stores/knowledgeBase.ts`, `frontend/src/views/DocumentsView.vue`, `tests/test_v071_document_lifecycle.py`, `tests/test_frontend_v071_document_lifecycle.py`, `tests/conftest.py`, `frontend/dist/**`
- verification: `python -m pytest tests/test_v071_document_lifecycle.py tests/test_frontend_v071_document_lifecycle.py -q` -> 5 passed; `python -m pytest tests/test_v071_document_lifecycle.py tests/test_v07_processing_spans.py tests/test_v05_document_management.py -q` -> 12 passed; `python -m pytest tests/test_frontend_v071_document_lifecycle.py tests/test_frontend_v071_upload_queue.py tests/test_frontend_v07_batch_progress.py tests/test_frontend_file_picker.py -q` -> 4 passed; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning; `python -m compileall app tests` -> exit 0.
- follow_ups: 自动进入 `TASK-022`。

### 2026-06-02 | TASK-022 | 停止生成、自动标题和 last-request state
- summary: Quick Answer stream 增加进程内 stop registry 和 `/chat-sessions/{session_id}/stop`；流式生成在 token 边界响应停止，保存 partial assistant message 为 cancelled；空/占位标题会在首问后生成可读标题；会话 `settings_json.last_request_state` 持久化 scope、检索命中、模型摘要、耗时和状态，前端展示最后一次请求并提供“停止生成”按钮。
- files: `app/api/v1/quick_answer.py`, `app/api/v1/chat_sessions.py`, `app/main.py`, `app/schemas/chat.py`, `app/services/chat.py`, `app/services/chat_stop.py`, `frontend/src/types/api.ts`, `frontend/src/stores/chat.ts`, `frontend/src/views/ChatView.vue`, `tests/test_v071_chat_generation_lifecycle.py`, `tests/test_frontend_v071_chat_generation_lifecycle.py`, `frontend/dist/**`
- verification: `python -m pytest tests/test_v071_chat_generation_lifecycle.py tests/test_frontend_v071_chat_generation_lifecycle.py -q` -> 4 passed; `python -m pytest tests/test_v071_chat_generation_lifecycle.py tests/test_v06_quick_answer_stream.py tests/test_v06_chat_sessions.py tests/test_v07_chat_experience.py tests/test_v07_chat_mentioned_items.py -q` -> 13 passed; `python -m pytest tests/test_frontend_v071_chat_generation_lifecycle.py tests/test_frontend_v06_chat.py tests/test_frontend_v07_chat_experience.py tests/test_frontend_v07_chat_mentions.py -q` -> 4 passed; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning; `python -m compileall app tests` -> exit 0.
- follow_ups: 自动进入 `TASK-023`。

### 2026-06-02 | TASK-023 | Retrieval trace 阶段化和真实运行状态
- summary: Quick Answer retrieval trace 新增 rewrite/search/rerank/answer 阶段列表，包含状态、耗时和输出摘要；新增 `/api/v1/runtime-status`，返回数据库、本地存储、向量库和 parser registry 的运行状态；设置页从 runtime status 加载 parser/storage/system 状态，Chat trace 面板展示阶段列表。
- files: `app/api/v1/runtime_status.py`, `app/api/v1/router.py`, `app/api/v1/quick_answer.py`, `app/services/quick_answer.py`, `frontend/src/types/api.ts`, `frontend/src/stores/retrieval.ts`, `frontend/src/views/SettingsView.vue`, `frontend/src/views/ChatView.vue`, `tests/test_v071_observability_status.py`, `tests/test_frontend_v071_observability_status.py`, `frontend/dist/**`
- verification: `python -m pytest tests/test_v071_observability_status.py tests/test_frontend_v071_observability_status.py -q` -> 3 passed; `python -m pytest tests/test_v071_observability_status.py tests/test_v06_quick_answer_stream.py tests/test_quick_answer.py tests/test_chunker_preview_api.py -q` -> 10 passed; `python -m pytest tests/test_frontend_v071_observability_status.py tests/test_frontend_v07_settings_shell.py tests/test_frontend_v071_chat_generation_lifecycle.py tests/test_frontend_v06_chat.py -q` -> 4 passed; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning; `python -m compileall app tests` -> exit 0.
- follow_ups: 自动进入 `TASK-024`。

### 2026-06-02 | TASK-024 | Command Palette 最小版
- summary: 新增全局 `CommandPalette`，支持按钮和 Ctrl/Meta+K 打开、按关键字过滤，并快速跳转快速问答、知识库、文档管理、FAQ 管理、模型配置、检索设置、解析器状态和存储状态；接入 `App.vue` 应用壳，不新增后端能力。
- files: `frontend/src/components/CommandPalette.vue`, `frontend/src/App.vue`, `tests/test_frontend_v071_command_palette.py`, `frontend/dist/**`
- verification: `python -m pytest tests/test_frontend_v071_command_palette.py -q` -> 1 passed; `python -m pytest tests/test_frontend_v071_command_palette.py tests/test_frontend_v071_observability_status.py tests/test_frontend_v071_chat_generation_lifecycle.py tests/test_frontend_v07_settings_shell.py tests/test_frontend_v06_chat.py -q` -> 5 passed; `python -m pytest (rg --files tests | rg 'test_frontend_.*\\.py$') -q` -> 29 passed; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning; `python -m compileall app tests` -> exit 0.
- follow_ups: v0.71 P0 `TASK-020` 到 `TASK-024` 已完成。

### 2026-05-31 | TASK-000 | 初始化 WeKnora 对齐开发循环
- summary: 创建 `docs/ai-loop` 任务看板；克隆 Tencent/WeKnora 到项目外只读参考目录；根据现有 gap analysis 和 WeKnora `e352721` README/CHANGELOG/source tree 整理第一批 v0.7 任务队列。未改动业务代码。
- files: `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`
- follow_ups: 从 `TASK-001` 开始，正式开工前等待用户确认。

### 2026-05-31 | TASK-001 | 知识库标签后端基础
- summary: 增加 KB-scoped 标签模型、Alembic migration、标签 CRUD API、文档/FAQ 批量标签分配、文档/FAQ 标签筛选，并把 `tag_id` 写入 Knowledge、FAQEntry、Chunk 和向量 payload。
- files: `alembic/versions/0010_v07_tags.py`, `app/db/models.py`, `app/db/repositories/tag.py`, `app/services/tags.py`, `app/api/v1/tags.py`, `app/schemas/tags.py`, `app/schemas/document.py`, `app/schemas/faq.py`, `app/api/v1/router.py`, `app/api/v1/documents.py`, `app/api/v1/knowledge_bases.py`, `app/api/v1/faqs.py`, `app/services/document.py`, `app/services/document_processing.py`, `app/services/faq.py`, `app/integrations/qdrant_store.py`, `tests/test_v07_tags.py`
- verification: `python -m pytest tests/test_v07_tags.py -q` -> 4 passed; `python -m pytest tests/test_v07_tags.py tests/test_v05_faq.py tests/test_v05_document_management.py tests/test_document_processing_chunk_payload.py tests/test_v03_knowledge_search.py -q` -> 15 passed; `python -m compileall app tests` -> exit 0; `ruff check .` -> All checks passed.
- follow_ups: 已按用户授权进入 `TASK-002`。

### 2026-05-31 | TASK-002 | 文档和 FAQ 标签前端体验
- summary: 在 Vue 工作台中加入标签类型和 store 方法；文档页支持标签筛选、新建/删除标签、导入时指定标签、批量设置文档标签、表格显示标签；FAQ 页支持标签筛选、创建/编辑时指定标签、列表中直接调整 FAQ 标签。
- files: `frontend/src/types/api.ts`, `frontend/src/stores/knowledgeBase.ts`, `frontend/src/views/DocumentsView.vue`, `frontend/src/views/FAQView.vue`, `tests/test_frontend_v07_tags.py`, `frontend/dist/**`
- verification: `python -m pytest tests/test_frontend_v07_tags.py -q` -> 1 passed; `npm --prefix frontend run build` -> exit 0; `python -m pytest (rg --files tests | rg 'test_frontend_.*\\.py$') -q` -> 13 passed. Browser plugin blocked local URL access by policy, so no browser screenshot was taken.
- follow_ups: 已按用户授权进入 `TASK-003`。

### 2026-05-31 | TASK-003 | 文档预览后端 API
- summary: 增加文档预览响应 schema、`DocumentPreviewService` 和 `/api/v1/documents/{document_id}/preview`，从已保存 chunks/pages 生成摘要、正文预览和 chunk outline，失败文档返回安全失败状态。
- files: `app/schemas/document.py`, `app/services/document_preview.py`, `app/api/v1/documents.py`, `tests/test_v07_document_preview.py`
- verification: `python -m pytest tests/test_v07_document_preview.py -q` -> 3 passed; `python -m pytest tests/test_v07_document_preview.py tests/test_v05_document_management.py tests/test_api_flow.py tests/test_parser.py -q` -> 11 passed; `python -m compileall app tests` -> exit 0; `ruff check .` -> All checks passed.
- follow_ups: 已按用户授权进入 `TASK-004`。

### 2026-05-31 | TASK-004 | 文档预览抽屉与 chunk 导航
- summary: 前端接入文档预览 API，新增预览类型和 store 方法；文档页将 chunks 抽屉升级为预览抽屉，展示摘要、状态、outline 和 chunk 内容，并支持从 outline 跳转到对应 chunk。
- files: `frontend/src/types/api.ts`, `frontend/src/stores/knowledgeBase.ts`, `frontend/src/views/DocumentsView.vue`, `frontend/src/styles/app.css`, `tests/test_frontend_v07_document_preview.py`, `frontend/dist/**`
- verification: `python -m pytest tests/test_frontend_v07_document_preview.py -q` -> 1 passed; `npm --prefix frontend run build` -> exit 0; `python -m pytest (rg --files tests | rg 'test_frontend_.*\\.py$') -q` -> 14 passed.
- follow_ups: 已按用户授权进入 `TASK-005`。

### 2026-05-31 | TASK-005 | FAQ 导入导出后端
- summary: 增加 FAQ CSV/XLSX 导入导出服务和 API；导入支持 append/replace、逐行失败摘要、metadata JSON、enabled、tag_id，并复用现有 FAQ 创建/删除和索引重建流程；导出支持 CSV 和 XLSX。
- files: `app/services/faq_import_export.py`, `app/api/v1/faqs.py`, `tests/test_v07_faq_import_export.py`
- verification: `python -m pytest tests/test_v07_faq_import_export.py -q` -> 3 passed; `python -m pytest tests/test_v07_faq_import_export.py tests/test_v05_faq.py tests/test_v07_tags.py tests/test_v03_knowledge_search.py -q` -> 13 passed; `python -m compileall app tests` -> exit 0; `ruff check .` -> All checks passed; `python -m pytest -q` -> 92 passed.
- follow_ups: 用户授权范围 TASK-001 到 TASK-005 已完成；队列下一项为 `TASK-006`。

### 2026-05-31 | TASK-006 | FAQ 导入导出和搜索测试面板
- summary: 前端 FAQ 页面接入导入弹窗、append/replace 模式、导入结果摘要和失败行展示；增加 CSV/XLSX 导出按钮；增加 FAQ 检索测试抽屉并复用现有 `/knowledge-search` 限定当前知识库。
- files: `frontend/src/utils/api.ts`, `frontend/src/types/api.ts`, `frontend/src/stores/knowledgeBase.ts`, `frontend/src/views/FAQView.vue`, `frontend/src/styles/app.css`, `tests/test_frontend_v07_faq_import_export.py`, `tests/test_frontend_api_errors.py`, `frontend/dist/**`
- verification: `python -m pytest tests/test_frontend_v07_faq_import_export.py -q` -> 1 passed; `python -m pytest tests/test_frontend_api_errors.py -q` -> 1 passed; `python -m pytest tests/test_frontend_v07_faq_import_export.py tests/test_frontend_api_errors.py -q` -> 2 passed; `python -m pytest (rg --files tests | rg 'test_frontend_.*\\.py$') -q` -> 15 passed; `npm --prefix frontend run build` -> exit 0; `python -m compileall app tests` -> exit 0; `ruff check .` -> All checks passed.
- follow_ups: 已按用户授权进入 `TASK-007`。

### 2026-05-31 | TASK-007 | 批处理进度和部分失败摘要
- summary: 批量重处理/删除响应新增 requested、succeeded、failed 和 failures；任务列表/详情新增 batch_summary，汇总同知识库同任务类型的总数、状态计数和失败原因；文档页新增批处理进度面板、失败原因展示和失败任务重试入口。
- files: `app/schemas/document.py`, `app/schemas/task.py`, `app/api/v1/tasks.py`, `app/api/v1/knowledge_bases.py`, `frontend/src/types/api.ts`, `frontend/src/stores/knowledgeBase.ts`, `frontend/src/views/DocumentsView.vue`, `frontend/src/styles/app.css`, `tests/test_v07_batch_progress.py`, `tests/test_frontend_v07_batch_progress.py`, `frontend/dist/**`
- verification: `python -m pytest tests/test_v07_batch_progress.py tests/test_frontend_v07_batch_progress.py -q` -> 3 passed; `python -m pytest tests/test_v07_batch_progress.py tests/test_v05_tasks.py tests/test_v05_document_management.py -q` -> 9 passed; `python -m pytest (rg --files tests | rg 'test_frontend_.*\\.py$') -q` -> 16 passed; `npm --prefix frontend run build` -> exit 0; `python -m compileall app tests` -> exit 0; `ruff check .` -> All checks passed.
- follow_ups: 已按用户授权进入 `TASK-008`。

### 2026-05-31 | TASK-008 | WeKnora-like 设置中心外壳
- summary: 新增 `/settings` 统一设置中心外壳和分区导航，复用现有模型、向量库、检索配置页面；侧边栏收敛为设置中心入口；新增解析器和存储状态面板，展示 builtin/local 已启用状态以及 MinerU/MinIO/S3/OSS/COS/OBS 等暂未启用 provider 占位。
- files: `frontend/src/views/SettingsView.vue`, `frontend/src/router/index.ts`, `frontend/src/components/AppSidebar.vue`, `frontend/src/styles/app.css`, `tests/test_frontend_v07_settings_shell.py`, `frontend/dist/**`
- verification: `python -m pytest tests/test_frontend_v07_settings_shell.py -q` -> 1 passed; `npm --prefix frontend run build` -> exit 0; `python -m pytest (rg --files tests | rg 'test_frontend_.*\\.py$') -q` -> 17 passed; `ruff check .` -> All checks passed; `python -m compileall app tests` -> exit 0.
- follow_ups: 已按用户授权进入 `TASK-009`。

### 2026-05-31 | TASK-009 | 会话搜索、批量删除和推荐问题
- summary: 会话列表支持按标题和消息内容搜索；新增会话批量软删除 API 和前端批量选择/删除入口；新增推荐问题 API，从 FAQ 和 chunk generated_questions 生成建议问题，并在新会话/空消息区展示可点击问题。
- files: `app/schemas/chat.py`, `app/db/repositories/chat.py`, `app/services/chat.py`, `app/api/v1/chat_sessions.py`, `frontend/src/types/api.ts`, `frontend/src/stores/chat.ts`, `frontend/src/views/ChatView.vue`, `tests/test_v07_chat_experience.py`, `tests/test_frontend_v07_chat_experience.py`, `frontend/dist/**`
- verification: `python -m pytest tests/test_v07_chat_experience.py tests/test_frontend_v07_chat_experience.py -q` -> 4 passed; `python -m pytest tests/test_v07_chat_experience.py tests/test_v06_chat_sessions.py tests/test_v06_quick_answer_stream.py -q` -> 9 passed; `python -m pytest (rg --files tests | rg 'test_frontend_.*\\.py$') -q` -> 18 passed; `npm --prefix frontend run build` -> exit 0; `python -m compileall app tests` -> exit 0; `ruff check .` -> All checks passed.
- follow_ups: 用户授权范围 TASK-006 到 TASK-009 已完成。

### 2026-05-31 | v0.61 | TASK-001 到 TASK-009 版本归档
- summary: 将 TASK-001 到 TASK-009 归档为 `v0.61`：标签体系、文档预览、FAQ 导入导出与搜索测试、批处理进度、设置中心外壳、会话搜索/批量删除/推荐问题，共同构成 v0.6 会话化 Quick Q&A 后的 WeKnora 对齐补强版本。
- files: `CHANGELOG.md`, `README.md`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`, `docs/weknora-visible-gap-analysis-v0.6-v0.7.zh-CN.md`, `docs/weknora-visible-gap-analysis-v0.6-v0.7.md`
- verification: 文档一致性检查和 markdown 文本搜索通过；详见本次文档更新验证。
- follow_ups: 后续任务应基于 v0.61 基线继续排队。

### 2026-05-31 | TASK-010 | KB capabilities 和 pin 后端基础
- summary: 增加单租户 KB pin 后端基础和 WeKnora-style capabilities 响应；新增 `knowledge_base_pins` 模型/migration、pin 读写仓库方法、`PUT /api/v1/knowledge-bases/{kb_id}/pin`，知识库读取/列表返回 `capabilities`、`is_pinned`、`pinned_at`，列表按 pin 状态置顶排序。
- files: `alembic/versions/0011_v07_kb_pins.py`, `app/db/models.py`, `app/db/repositories/knowledge_base.py`, `app/schemas/knowledge_base.py`, `app/services/knowledge_base.py`, `app/api/v1/knowledge_bases.py`, `tests/test_v07_kb_capabilities_pin.py`
- verification: `python -m pytest tests/test_v07_kb_capabilities_pin.py -q` -> 4 passed; `python -m pytest tests/test_v07_kb_capabilities_pin.py tests/test_v021_crud_endpoints.py tests/test_v05_document_management.py tests/test_v07_tags.py -q` -> 15 passed; `python -m compileall app tests` -> exit 0; `ruff check .` -> All checks passed; `python -m pytest -q` -> 105 passed.
- follow_ups: 自动进入 `TASK-011`。

### 2026-05-31 | TASK-011 | KB pin 和 capabilities 前端展示
- summary: 前端知识库列表接入 TASK-010 的 `capabilities`、`is_pinned` 和 `pinned_at` 字段；新增 pin/unpin 操作、置顶状态展示、能力标签组和 Wiki/Graph 禁用占位，并通过 store 调用 `PUT /api/v1/knowledge-bases/{kb_id}/pin` 刷新列表排序。
- files: `frontend/src/types/api.ts`, `frontend/src/stores/knowledgeBase.ts`, `frontend/src/views/KnowledgeBaseView.vue`, `frontend/src/styles/app.css`, `tests/test_frontend_v07_kb_pin_capabilities.py`
- verification: `python -m pytest tests/test_frontend_v07_kb_pin_capabilities.py -q` -> 1 passed; `npm --prefix frontend run build` -> exit 0; `python -m pytest (rg --files tests | rg 'test_frontend_.*\\.py$') -q` -> 19 passed; `ruff check .` -> All checks passed; `python -m compileall app tests` -> exit 0; `python -m pytest -q` -> 106 passed.
- follow_ups: 自动进入 `TASK-012`。

### 2026-05-31 | TASK-012 | WeKnora-like KB 详情一体化页面骨架
- summary: 新增 `KnowledgeBaseDetailView.vue` 和 `/knowledge-bases/:kbId` 路由，按 KB 类型默认展示文档或 FAQ 工作流；详情页收敛概览、文档管理、FAQ 管理、设置、任务/状态入口，并将 Wiki/Graph 保持为禁用占位；创建和列表详情入口默认进入 KB detail，旧 documents/faqs 路由继续可用。
- files: `frontend/src/views/KnowledgeBaseDetailView.vue`, `frontend/src/router/index.ts`, `frontend/src/views/KnowledgeBaseView.vue`, `frontend/src/styles/app.css`, `tests/test_frontend_v07_kb_detail_shell.py`
- verification: `python -m pytest tests/test_frontend_v07_kb_detail_shell.py -q` -> 1 passed; `npm --prefix frontend run build` -> exit 0; `python -m pytest (rg --files tests | rg 'test_frontend_.*\\.py$') -q` -> 20 passed; `ruff check .` -> All checks passed; `python -m compileall app tests` -> exit 0; `python -m pytest -q` -> 107 passed.
- follow_ups: 自动进入 `TASK-013`。

### 2026-05-31 | TASK-013 | KB 设置面板支持创建后编辑模型、parser、chunking 和 indexing
- summary: 在 KB detail 设置区新增 WeKnora-like 轻量配置面板，覆盖基础信息、QA/Embedding 模型、parser rules、chunking config、indexing strategy 和 vector store；保存复用 `PUT /api/v1/knowledge-bases/{kb_id}`，成功后提示需要重处理/重建索引，并提供立即重建入口；后端模型类型错误改为更明确中文提示。
- files: `frontend/src/views/KnowledgeBaseDetailView.vue`, `frontend/src/styles/app.css`, `app/services/model_config.py`, `tests/test_frontend_v07_kb_settings_panel.py`, `tests/test_v07_kb_settings_update.py`
- verification: `python -m pytest tests/test_frontend_v07_kb_settings_panel.py -q` -> 1 passed; `python -m pytest tests/test_v07_kb_settings_update.py -q` -> 2 passed; `npm --prefix frontend run build` -> exit 0; `python -m pytest (rg --files tests | rg 'test_frontend_.*\\.py$') -q` -> 21 passed; `python -m pytest tests/test_v07_kb_settings_update.py tests/test_v07_kb_capabilities_pin.py tests/test_v021_crud_endpoints.py tests/test_v05_indexing_strategy.py -q` -> 13 passed; `ruff check .` -> All checks passed; `python -m compileall app tests` -> exit 0; `python -m pytest -q` -> 110 passed.
- follow_ups: 自动进入 `TASK-014`。

### 2026-05-31 | TASK-014 | 多知识库和文件范围检索后端
- summary: 扩展 `knowledge-search` 和 `quick-answer` 的 scope schema，支持 WeKnora-style `knowledge_base_ids` 与 `knowledge_ids`；检索服务会合并单 KB、多 KB和文件范围，反查文件所属 KB，校验跨 KB Embedding 模型一致性，并按 KB fan-out 检索后合并去重；sources 新增 `knowledge_base_name`；keyword/vector/hybrid retriever 支持文件过滤且保留旧 fake retriever 兼容。
- files: `app/schemas/knowledge_search.py`, `app/schemas/quick_answer.py`, `app/services/knowledge_search.py`, `app/services/quick_answer.py`, `app/api/v1/knowledge_search.py`, `app/api/v1/quick_answer.py`, `app/rag/retriever/__init__.py`, `app/db/repositories/chunk.py`, `app/integrations/qdrant_store.py`, `app/rag/quick_answer.py`, `frontend/src/types/api.ts`, `tests/test_v07_multi_scope_retrieval.py`
- verification: `python -m pytest tests/test_v07_multi_scope_retrieval.py -q` -> 5 passed; `python -m pytest tests/test_v07_multi_scope_retrieval.py tests/test_v03_knowledge_search.py tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_v06_chat_sessions.py -q` -> 17 passed; `npm --prefix frontend run build` -> exit 0; `python -m pytest (rg --files tests | rg 'test_frontend_.*\\.py$') -q` -> 21 passed; `ruff check .` -> All checks passed; `python -m compileall app tests` -> exit 0; `python -m pytest -q` -> 115 passed.
- follow_ups: 自动进入 `TASK-015`。

### 2026-05-31 | TASK-015 | Chat mention 选择器和多 scope 问答体验
- summary: Chat 工作台新增显式 KB/file scope 选择和 mention chips；发送与检索调试会提交 `knowledge_base_ids`、`knowledge_ids` 和 `mentioned_items`，未选择 scope 时继续使用当前单 KB；用户消息持久化并展示 mentioned_items，SourceCard 展示 `knowledge_base_name` 真实来源。
- files: `frontend/src/views/ChatView.vue`, `frontend/src/stores/chat.ts`, `frontend/src/types/api.ts`, `frontend/src/components/SourceCard.vue`, `app/schemas/quick_answer.py`, `app/schemas/chat.py`, `app/services/chat.py`, `app/api/v1/quick_answer.py`, `tests/test_frontend_v07_chat_mentions.py`, `tests/test_v07_chat_mentioned_items.py`
- verification: `python -m pytest tests/test_frontend_v07_chat_mentions.py -q` -> 1 passed; `python -m pytest tests/test_v07_chat_mentioned_items.py -q` -> 1 passed; `npm --prefix frontend run build` -> exit 0; `python -m pytest tests/test_v07_chat_mentioned_items.py tests/test_v07_multi_scope_retrieval.py tests/test_v06_quick_answer_stream.py tests/test_v06_chat_sessions.py tests/test_v07_chat_experience.py -q` -> 15 passed; `python -m pytest (rg --files tests | rg 'test_frontend_.*\\.py$') -q` -> 22 passed; `ruff check .` -> All checks passed; `python -m compileall app tests` -> exit 0; `python -m pytest -q` -> 117 passed.
- follow_ups: 自动进入 `TASK-016`。

### 2026-05-31 | TASK-016 | 文档处理 spans/timeline 后端
- summary: 增加 WeKnora-style 文档处理 timeline 后端基础；新增 `knowledge_processing_spans` 模型和 migration、`ProcessingSpanService` 轻量 tracker、`GET /api/v1/documents/{document_id}/spans`，并在文档处理流程中记录 parse、chunk、embed、upsert、finalize 五阶段状态、耗时、错误和 downstream cancelled；旧文档无 spans 时返回安全占位。
- files: `alembic/versions/0012_v07_processing_spans.py`, `app/db/models.py`, `app/schemas/processing_span.py`, `app/services/processing_spans.py`, `app/services/document_processing.py`, `app/api/v1/documents.py`, `tests/test_v07_processing_spans.py`
- verification: `python -m pytest tests/test_v07_processing_spans.py -q` -> 4 passed; `python -m pytest tests/test_v07_processing_spans.py tests/test_document_processing_chunk_payload.py tests/test_v02_model_binding_reprocess.py tests/test_v07_document_preview.py tests/test_v05_document_management.py tests/test_v03_knowledge_search.py -q` -> 22 passed; `ruff check .` -> All checks passed; `python -m compileall app tests` -> exit 0; `python -m pytest -q` -> 121 passed.
- follow_ups: 自动进入 `TASK-017`。

### 2026-05-31 | TASK-017 | 文档处理 timeline 前端
- summary: 前端接入 TASK-016 spans API；新增 `ProcessingSpanTimeline` 类型、store 的 `loadDocumentSpans`，文档列表对 pending/processing/failed 文档提供“处理时间线”入口，预览抽屉和单独抽屉展示五阶段状态、耗时、错误和手动刷新，旧文档 attempt 0 显示可读占位。
- files: `frontend/src/types/api.ts`, `frontend/src/stores/knowledgeBase.ts`, `frontend/src/views/DocumentsView.vue`, `frontend/src/styles/app.css`, `tests/test_frontend_v07_processing_timeline.py`
- verification: `python -m pytest tests/test_frontend_v07_processing_timeline.py -q` -> 1 passed; `npm --prefix frontend run build` -> exit 0; `python -m pytest (rg --files tests | rg 'test_frontend_.*\\.py$') -q` -> 23 passed; `ruff check .` -> All checks passed; `python -m compileall app tests` -> exit 0; `python -m pytest -q` -> 122 passed; Playwright with fetch stubs confirmed the timeline drawer renders failed/cancelled stages and error text.
- follow_ups: 自动进入 `TASK-018`。

### 2026-05-31 | TASK-018 | FAQ similar questions 和索引模式后端
- summary: 增加 WeKnora-style FAQ 相似问和索引模式后端；KB schema/model 支持 `faq_config.index_mode` 与 `faq_config.question_index_mode`，FAQ entry 支持 `similar_questions`；导入导出新增 `similar_questions` 列；FAQ 索引按 question_only/question_answer 与 combined/separate 生成 chunk、search_text、向量 payload，并在 metadata 标记 `standard_question`、`similar_questions`、`matched_question` 和 `question_role`。
- files: `alembic/versions/0013_v07_faq_similar_indexing.py`, `app/db/models.py`, `app/schemas/knowledge_base.py`, `app/schemas/faq.py`, `app/services/knowledge_base.py`, `app/api/v1/knowledge_bases.py`, `app/services/faq.py`, `app/services/faq_import_export.py`, `tests/test_v07_faq_similar_indexing.py`, `tests/test_v07_faq_import_export.py`
- verification: `python -m pytest tests/test_v07_faq_similar_indexing.py -q` -> 2 passed; `python -m pytest tests/test_v07_faq_similar_indexing.py tests/test_v05_faq.py tests/test_v07_faq_import_export.py tests/test_v07_kb_settings_update.py tests/test_v07_multi_scope_retrieval.py tests/test_v03_knowledge_search.py -q` -> 18 passed; `ruff check .` -> All checks passed; `python -m compileall app tests` -> exit 0; `npm --prefix frontend run build` -> exit 0; `python -m pytest -q` -> 124 passed.
- follow_ups: 自动进入 `TASK-019`。

### 2026-05-31 | TASK-019 | FAQ similar questions 和索引模式前端
- summary: 前端接入 TASK-018；FAQ 类型和 store 支持 `similar_questions` 与 `faq_config`；FAQ 管理页展示相似问法、创建/编辑弹窗可输入相似问法并去重过滤、导入说明包含 `similar_questions` 列、检索测试展示 `matched_question`；KB 详情设置区新增 FAQ index mode 和 question index mode 表单并随保存提交。
- files: `frontend/src/types/api.ts`, `frontend/src/stores/knowledgeBase.ts`, `frontend/src/views/FAQView.vue`, `frontend/src/views/KnowledgeBaseDetailView.vue`, `frontend/src/styles/app.css`, `tests/test_frontend_v07_faq_similar_indexing.py`
- verification: `python -m pytest tests/test_frontend_v07_faq_similar_indexing.py -q` -> 1 passed; `npm --prefix frontend run build` -> exit 0; `python -m pytest (rg --files tests | rg 'test_frontend_.*\\.py$') -q` -> 24 passed; `ruff check .` -> All checks passed; `python -m compileall app tests` -> exit 0; `python -m pytest -q` -> 125 passed; Playwright with fetch stubs confirmed FAQ list renders similar questions and search drawer renders matched question.
- follow_ups: v0.7 P0 队列完成；后续 v0.71 P0 已在 TASK-020 到 TASK-024 落地。

### 2026-06-01 | v0.7 | 文档归档
- summary: 将项目文档更新到当前版本 `v0.7`：README 当前版本、v0.7 Schema/API 变化、CHANGELOG v0.7 条目、AI Task Board 基线、v0.7 对比路线文档和 v0.6-v0.7 差距分析均补充 TASK-010 到 TASK-019 完成状态。
- files: `README.md`, `CHANGELOG.md`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`, `docs/weknora-local-comparison-v0.7-roadmap.zh-CN.md`, `docs/weknora-visible-gap-analysis-v0.6-v0.7.zh-CN.md`, `docs/weknora-visible-gap-analysis-v0.6-v0.7.md`
- verification: 文档版本文本搜索、README schema 字段核对和 git diff 范围检查通过。
- follow_ups: v0.71 P0 已完成；剩余 P1/P2 和 v0.72 候选继续保留在 `docs/ai-loop/requirements.md` Parking Lot。

## Entry Template
### YYYY-MM-DD | TASK-000 | Short summary
- summary: What was delivered.
- files: path/to/file
- follow_ups: none

### 2026-06-06 | TASK-046 | v0.9 固定检索配置和默认参数
- summary: 收敛 v0.9 固定 RAG 主链路配置；retrieval config 服务层固定 hybrid/qdrant/paradedb_bm25、RRF、rerank、parent-child 和上下文参数，仅保留 rerank_model_id 作为模型绑定；新建 KB 默认开启 parent-child/rerank 并归一化禁用输入；Quick Q&A 和 knowledge search 忽略旧 vector_only/keyword_only 请求，trace/diagnostics 回写实际 hybrid 主链路；FAQ boost 在 hybrid RRF 后继续按原始 vector/keyword 置信度判断。
- files: `app/schemas/retrieval.py`, `app/services/retrieval_config.py`, `app/services/knowledge_base.py`, `app/schemas/knowledge_base.py`, `app/services/knowledge_search.py`, `app/services/quick_answer.py`, `tests/test_v09_fixed_retrieval_config.py`, `tests/test_v05_indexing_strategy.py`, `tests/test_v03_knowledge_search.py`, `tests/test_quick_answer.py`, `docs/ai-loop/requirements.md`, `docs/superpowers/plans/2026-06-06-v09-task-046-055.md`
- verification: `python -m pytest tests/test_v09_fixed_retrieval_config.py -q` -> 3 passed; `python -m pytest tests/test_v05_indexing_strategy.py tests/test_v03_knowledge_search.py tests/test_quick_answer.py tests/test_v09_fixed_retrieval_config.py -q` -> 23 passed; `python -m compileall app tests` -> exit 0; `ruff check app tests` -> All checks passed.
- follow_ups: 自动进入 `TASK-047`。

### 2026-06-06 | TASK-047 | 固定 parent-child chunk 数据契约
- summary: 文档处理固定使用 parent-child chunking 和 auto 策略归一；parent chunks 只入库用于上下文，child chunks 用于 embedding/retrieval；child chunk metadata 和 Qdrant payload 补齐 tenant_id、knowledge_base_id、document_id、child_chunk_id、parent_chunk_id、title、context_header、chunk_type、position/index、normalized_content/search_text；旧 enable_parent_child=false 输入不再让新处理任务退回单层 chunk；generated questions 更新同步 search_text 到向量 payload。
- files: `app/services/knowledge_base.py`, `app/services/document_processing.py`, `app/services/chunk.py`, `tests/test_document_processing_chunk_payload.py`, `tests/test_v08_chunks_api.py`, `docs/ai-loop/requirements.md`
- verification: `python -m pytest tests/test_document_processing_chunk_payload.py -q` -> 2 passed; `python -m pytest tests/test_chunker.py tests/test_document_processing_chunk_payload.py tests/test_v08_chunks_api.py -q` -> 11 passed; `python -m compileall app tests` -> exit 0; `ruff check app tests` -> All checks passed.
- follow_ups: 自动进入 `TASK-048`。

### 2026-06-06 | TASK-048 | ParadeDB BM25 schema 和 repository 边界
- summary: 新增 v0.9 ParadeDB pg_search BM25 migration；repository 层将 PostgreSQL keyword search 切换为 ParadeDB BM25 SQL，使用 `search_text ||| :query`、`pdb.score(id)` 和 `pdb.snippet(search_text)`，并限定 child chunks；ParadeDB 缺失时返回中文可读错误；保留 SQLite/fake fallback 供自动测试；补充 BM25 upsert/delete repository 边界方法。
- files: `alembic/versions/0017_v09_paradedb_bm25.py`, `app/db/repositories/chunk.py`, `tests/test_v09_paradedb_bm25.py`, `docs/ai-loop/requirements.md`
- verification: `python -m pytest tests/test_v09_paradedb_bm25.py -q` -> 3 passed; `python -m pytest tests/test_v03_retriever.py tests/test_v03_knowledge_search.py tests/test_v09_paradedb_bm25.py -q` -> 24 passed; `alembic upgrade 0016_task032_faq_recommended:head --sql | Select-String ...` -> confirmed `CREATE EXTENSION IF NOT EXISTS pg_search`, `USING bm25`, `ix_chunks_paradedb_bm25`; `python -m compileall app tests` -> exit 0; `ruff check app tests` -> All checks passed. Online `alembic upgrade head` was attempted with `connect_timeout=3` and failed because local Postgres at `localhost:15432` timed out; Docker Desktop API was unavailable, so real ParadeDB migration could not be exercised in this environment.
- follow_ups: 自动进入 `TASK-049`。

### 2026-06-06 | TASK-049 | 文档处理双写 Qdrant 和 ParadeDB BM25
- summary: 文档处理 upsert 阶段固定清理旧 Qdrant/BM25，再写入 PostgreSQL chunks、BM25 child chunks 边界和 Qdrant child payload；BM25 upsert 失败会让处理进入 failed 状态并保留中文错误，不再假装 completed；文档和知识库软删除同步调用 BM25 delete 与向量删除。
- files: `app/services/document_processing.py`, `app/services/document.py`, `app/services/knowledge_base.py`, `tests/test_document_processing_chunk_payload.py`, `tests/test_v071_document_lifecycle.py`, `docs/ai-loop/requirements.md`
- verification: `python -m pytest tests/test_document_processing_chunk_payload.py tests/test_v071_document_lifecycle.py -q` -> 8 passed; `python -m pytest tests/test_document_processing_chunk_payload.py tests/test_v071_document_lifecycle.py tests/test_v03_knowledge_search.py -q` -> 15 passed; `python -m compileall app tests` -> exit 0; `ruff check app tests` -> All checks passed.
- follow_ups: 自动进入 `TASK-050`。

### 2026-06-06 | TASK-050 | 固定 Quick Q&A hybrid 检索入口
- summary: 从公开 Quick Q&A 和 knowledge search 请求 schema 移除旧 `mode` 字段，路由和 service 不再传递用户 mode；旧请求体里的 `mode` 作为 extra 被忽略，实际 trace 固定为 hybrid；Quick Q&A stream 固定启用 query rewrite 入口，无历史时明确 skipped；新增验证 vector/keyword top50 与 RRF top30。
- files: `app/schemas/knowledge_search.py`, `app/schemas/quick_answer.py`, `app/api/v1/knowledge_search.py`, `app/api/v1/quick_answer.py`, `app/services/knowledge_search.py`, `app/services/quick_answer.py`, `tests/test_v09_hybrid_entry.py`, `tests/test_v06_quick_answer_stream.py`, `docs/ai-loop/requirements.md`
- verification: `python -m pytest tests/test_v09_hybrid_entry.py -q` -> 2 passed; `python -m pytest tests/test_v03_knowledge_search.py tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_v09_hybrid_entry.py -q` -> 25 passed; `python -m compileall app tests` -> exit 0; `ruff check app tests` -> All checks passed.
- follow_ups: 自动进入 `TASK-051`。

### 2026-06-06 | TASK-051 | mandatory rerank
- summary: 将 Quick Q&A rerank 收敛为 v0.9 必需阶段；有候选命中时即使旧请求传 `enable_rerank=false` 也必须执行 rerank；缺少 rerank 模型配置时非流式和流式 Quick Q&A 均返回中文硬错误；rerank provider 调用失败不再静默 fallback；trace 记录 rerank_input_count、rerank_output_count、model_config_used 和耗时。
- files: `app/services/knowledge_search.py`, `tests/test_model_config_required.py`, `tests/test_v03_knowledge_search.py`, `tests/test_quick_answer.py`, `tests/test_v06_quick_answer_stream.py`, `tests/test_v09_hybrid_entry.py`, `docs/ai-loop/requirements.md`
- verification: `python -m pytest tests/test_model_config_required.py tests/test_v03_retriever.py tests/test_v03_knowledge_search.py tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_v09_hybrid_entry.py -q` -> 43 passed; `python -m compileall app tests` -> exit 0; `ruff check .` -> All checks passed.
- follow_ups: 自动进入 `TASK-052`。

### 2026-06-06 | TASK-052 | parent context、sources 和 retrieval trace 最终契约
- summary: 将 parent_expand 调整到 rerank 之后，使 rerank 选出的 child hits 再扩展 parent context；Quick Q&A 新增最终 context_select，按 parent/context 去重、编号、限制 6 段和 8000 字符；LLM prompt 使用编号后的 parent context；sources 补充 document_title、source_type、snippet 并保留 child chunk identity 和 parent_chunk_id；流式和非流式 trace 均输出 query_original/query_normalized/query_rewritten、vector/keyword/rrf/rerank hit counts、selected_contexts 和安全的 model_config_used。
- files: `app/services/knowledge_search.py`, `app/services/quick_answer.py`, `app/rag/quick_answer.py`, `app/schemas/quick_answer.py`, `app/api/v1/quick_answer.py`, `tests/test_quick_answer.py`, `tests/test_v06_quick_answer_stream.py`, `tests/test_v071_observability_status.py`, `tests/test_v09_hybrid_entry.py`, `docs/ai-loop/requirements.md`
- verification: `python -m pytest tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_v071_observability_status.py -q` -> 19 passed; `python -m pytest tests/test_v03_knowledge_search.py tests/test_model_config_required.py tests/test_v09_hybrid_entry.py tests/test_v09_fixed_retrieval_config.py tests/test_v03_retriever.py tests/test_quick_answer.py tests/test_v06_quick_answer_stream.py tests/test_v071_observability_status.py -q` -> 49 passed; `python -m compileall app tests` -> exit 0; `ruff check .` -> All checks passed.
- follow_ups: 自动进入 `TASK-053`。

### 2026-06-06 | TASK-053 | 前端设置页收敛为 v0.9 固定主链路
- summary: 前端设置页改为展示 v0.9 固定主链路状态：Qdrant dense、ParadeDB BM25、RRF、必需 rerank 和固定 parent-child；移除 retrieval mode 选择、rerank 关闭开关、parent-child 关闭开关和 planned vector backend 列表；VectorStore 设置页只展示 Qdrant 配置状态和静态字段说明，配置对象以安全 JSON 展示；知识库创建/编辑和详情设置固定提交 parent-child/rerank true。
- files: `frontend/src/views/RetrievalSettingsView.vue`, `frontend/src/views/VectorStoreSettingsView.vue`, `frontend/src/views/KnowledgeBaseView.vue`, `frontend/src/views/KnowledgeBaseDetailView.vue`, `frontend/src/stores/retrieval.ts`, `frontend/src/types/api.ts`, `tests/test_frontend_v03_retrieval.py`, `tests/test_frontend_v02_model_management.py`, `tests/test_frontend_chunking_settings.py`, `docs/ai-loop/requirements.md`
- verification: `python -m pytest tests/test_frontend_v03_retrieval.py tests/test_frontend_v02_model_management.py tests/test_frontend_v071_observability_status.py tests/test_frontend_chunking_settings.py -q` -> 11 passed; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning; `python -m compileall app tests` -> exit 0; `ruff check .` -> All checks passed; browser check at `http://127.0.0.1:5173/#/settings?section=retrieval` confirmed fixed mainline text present and old mode/rerank/parent-child switch test ids absent.
- follow_ups: 自动进入 `TASK-054`。

### 2026-06-06 | TASK-054 | 前端 Quick Q&A sources 和 retrieval trace 展示
- summary: Quick Q&A 展示层补齐 v0.9 sources 与 trace：SourceCard 展示 document_title、snippet、source_type、score、rerank_score、chunk_id、parent_chunk_id 和 metadata 摘要；Chat trace 展示 query_original/query_normalized/query_rewritten、vector/keyword/rrf/rerank hit counts、context_select 阶段和 selected_contexts 列表；trace value 继续经安全格式化，避免 `[object Object]`。
- files: `frontend/src/components/SourceCard.vue`, `frontend/src/views/ChatView.vue`, `frontend/src/types/api.ts`, `tests/test_frontend_v06_chat.py`, `docs/ai-loop/requirements.md`
- verification: `python -m pytest tests/test_frontend_v06_chat.py tests/test_frontend_v07_chat_experience.py tests/test_frontend_v071_observability_status.py -q` -> 8 passed; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning; `python -m compileall app tests` -> exit 0; `ruff check .` -> All checks passed; browser check at `http://127.0.0.1:5173/#/chat` confirmed Chat page renders and empty state contains no `[object Object]`.
- follow_ups: 自动进入 `TASK-055`。

### 2026-06-06 | TASK-055 | v0.9 端到端验收和文档更新
- summary: 完成 v0.9 固定 Quick Q&A 主链路收尾验收；README/CHANGELOG/任务板更新为 v0.9，说明 Qdrant + ParadeDB BM25 + RRF + mandatory rerank + parent-child context 的固定依赖、配置步骤、schema/trace/sources 契约和真实验收状态；旧测试按 v0.9 固定链路更新，显式绑定 fake rerank 并改为断言 parent-child、mandatory rerank、ParadeDB diagnostics 和固定前端配置。
- files: `README.md`, `CHANGELOG.md`, `docs/v0.9.md`, `docs/ai-loop/requirements.md`, `docs/ai-loop/done.md`, `docs/superpowers/plans/2026-06-06-v09-task-046-055.md`, `tests/conftest.py`, `tests/test_api_flow.py`, `tests/test_v02_model_binding_reprocess.py`, `tests/test_v05_faq.py`, `tests/test_v071_chat_generation_lifecycle.py`, `tests/test_v07_faq_similar_indexing.py`, `tests/test_v07_kb_capabilities_pin.py`, `tests/test_v07_kb_settings_update.py`, `tests/test_v07_multi_scope_retrieval.py`, `tests/test_v08_chunks_api.py`
- verification: `python -m pytest -q` -> 209 passed; `ruff check .` -> All checks passed; `python -m compileall app tests` -> exit 0; `npm --prefix frontend run build` -> passed with existing Vite large chunk warning; `alembic upgrade 0016_task032_faq_recommended:head --sql | Select-String -Pattern "pg_search|USING bm25|ix_chunks_paradedb_bm25"` -> confirmed pg_search extension and BM25 index SQL; browser settings/chat smoke passed from TASK-053/TASK-054 local Vite check. Docker Desktop 可用后补验：`docker compose up -d --build` -> `api / worker / postgres / redis / qdrant` all healthy, `api` online migration passed with `pg_search 0.24.0` and `ix_chunks_paradedb_bm25`; local-service E2E with real PostgreSQL/ParadeDB + Qdrant and fake model clients verified KB create, document upload, synchronous processing, parent-child chunks, Qdrant point, ParadeDB BM25 hit, knowledge-search and quick-answer trace/sources. 2026-06-08 启动脚本补验：`scripts/start-dev.ps1` -> Docker backend stack and local Vite started, `/health` ok, frontend 5173 returned 200, Celery ping showed one Docker worker online.
- follow_ups: TASK-046 到 TASK-055 全部完成；按用户要求停工。
