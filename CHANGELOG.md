# Changelog

## v0.92

v0.92 是 v0.91 之后的解析能力和模型配置体验版本。主链路继续保持 WeKnora-style 固定 Quick Q&A：Query Understand + Qdrant dense + ParadeDB BM25 + RRF + mandatory rerank + parent-child context；本版本重点把文档解析从 builtin 扩展到 MinerU 标准精准解析，并补齐大 PDF 自动分片。

### Added

- 新增解析器配置中心：
  - 新增独立 `parser_provider_configs` 表，不复用模型配置表。
  - 新增 `/api/v1/parser-configs` 和 `/api/v1/parser-configs/{provider}` 系列 API。
  - MinerU API Key 使用后端加密保存，读取接口只返回 `api_key_configured` 和 `api_key_last4`。
- 新增 MinerU 标准精准解析：
  - 默认 `provider=mineru`、`base_url=https://mineru.net/api/v4`、`model_version=vlm`、`language=ch`。
  - 通过批量签名 URL 上传原文件、异步轮询解析结果、下载 zip 并读取 `full.md`。
  - `document.doc_metadata` 写入 `mineru_batch_id`、`mineru_state`、`mineru_trace_id`、`full_zip_url`、`model_version` 和输出文件摘要。
- 新增默认 parser rules：
  - `pdf/doc/docx/ppt/pptx/xls/xlsx/png/jpg/jpeg/jp2/webp/gif/bmp` 默认走 MinerU。
  - `txt/md/markdown/csv/json` 继续走 builtin。
  - 既有文档知识库迁移到 MinerU 规则，文本类规则保留 builtin。
- 新增 PDF 超 200 页自动分片：
  - 本地使用 `pypdf` 读取页数并按 200 页生成临时 PDF 分片。
  - 逐片调用 MinerU，合并 Markdown 时插入 `## 第 x-y 页` 标题。
  - 文档元数据记录 `mineru_split`、`mineru_split_part_count`、`mineru_split_max_pages`、`page_count` 和 `mineru_parts`。
  - 任一分片失败时整个文档解析失败，错误包含分片序号和页码范围。
- 前端设置中心新增“解析器”页，支持配置 MinerU Key、查看尾号、保存 `vlm/ch/表格/公式/OCR` 等参数；文档上传 accept 扩展到 MinerU 支持格式。

### Fixed

- 修复 DeepSeek QA 模型名被 provider preset 重置的问题；保存 `deepseek-v4-pro` 等自定义模型名后不再回落到 `deepseek-chat`。
- 修复模型测试失败时前端仍显示成功样式的问题；现在会按 `chat_ok/embedding_ok/rerank_ok` 判断，并展示中文可读错误。

### Changed

- 解析模块从“仅 builtin/占位 MinerU 状态”升级为正式 provider registry + provider config 路径。
- MinerU 缺少配置、Token 错误、任务失败、超时、zip 缺少 Markdown、PDF 加密或页数读取失败都会返回中文明确错误，不静默回退 builtin。
- v0.92 后续质量优化方向转为量化评测闭环：优先建设 RAG eval 数据集、retrieval Recall@K/MRR/nDCG、answer faithfulness/relevancy 和 source hit rate。

### Not Included

- 非 PDF 文件超过 MinerU 页数限制时，v0.92 暂不自动拆分；需要人工拆分或后续增加 Office 转 PDF 后分片。
- 不接入离线 MinerU、本地 OCR/VLM/ASR 或 WeKnoraCloud。
- 不内置 DeepEval/Ragas/Phoenix 评测平台；本版本仅记录下一阶段评测方向。

### Verification

- `python -m pytest tests/test_mineru_integration.py -q`：`8 passed`
- `python -m pytest tests/test_mineru_integration.py tests/test_document_processing_chunk_payload.py tests/test_v07_processing_spans.py -q`：`17 passed`
- `python -m pytest -q`：`233 passed`
- `ruff check .`：通过
- `python -m compileall app tests`：通过
- `npm --prefix frontend run build`：通过，仍有既有 Vite large chunk warning。
- Browser mock smoke：模型设置页保存 `deepseek-v4-pro` 后不会被重置为 `deepseek-chat`；模型测试失败时显示 error message，而不是成功提示。

## v0.91

v0.91 是 v0.9 固定 Quick Q&A 主链路后的质量修复版本，重点解决真实运行态召回差、rerank 错排和 Chat 前端交互问题。主链路仍保持 WeKnora-style 固定链路：Query Understand + Qdrant dense + ParadeDB BM25 + RRF + mandatory rerank + parent-child context。

### Fixed

- 修复真实运行态中 embedding 配置维度与 Qdrant collection 维度不一致导致 `vector_hits=0` 的问题定位与本地配置修正：
  - 现象：KB 的向量点在 `knowmate_embeddings_1024`，但模型配置被改为 `embedding_dimension=512`，查询会查不存在的 `knowmate_embeddings_512`。
  - 处理：本地运行库将 `text-embedding-v4` 配置恢复为 1024 维；文档补充“切换 embedding 维度后必须重处理文档或保持配置与已入库向量一致”的排障规则。
- 修复 rerank 模型分过度主导导致错误主题条文排在目标条文前的问题：
  - `RerankPipeline` composite score 增加 query lexical coverage。
  - `score_details` 追加 `lexical_score`，便于解释为什么目标 chunk 被提升或错误 chunk 被压低。
  - FAQ 候选不使用通用 lexical 纠偏，继续由 FAQ merge / boost 策略控制，避免低置信 FAQ 被误提权。
- 修复 parent chunk 进入初始候选后可能覆盖 child identity 的问题；vector / keyword 初始候选过滤 parent chunk，保持“child 检索、parent 回答上下文”契约。
- 修复 Quick Answer 默认 prompt 过度保守的问题；当上下文包含可适用规则时，模型应基于上下文做规则适用分析，不应仅因用户事实没有逐字出现在上下文中就回答“知识库不足”。

### Changed

- Chat 前端品牌和导航口径调整：
  - 左上角品牌改为 `knowmate知友`。
  - 侧边栏“开放能力”改为“设置”。
  - 移除右下角用户头像/身份标识区域，当前版本不继续展示 RBAC 相关入口。
- Chat 消息滚动交互调整：
  - 发送消息后自动滚动到底部。
  - 流式生成 token 时持续跟随到底部。
  - 用户主动上滑或滚轮离开底部时暂停自动跟随，滚回底部附近后恢复。
  - 消息列表底部留白增加，减少回答内容被输入框遮挡。

### Verification

- `python -m pytest -q`：`220 passed`
- `ruff check app/rag/prompt.py app/rag/retriever/__init__.py app/services/knowledge_search.py tests/test_quick_answer.py tests/test_v03_retriever.py`：通过
- `python -m compileall app tests`：通过
- `python -m pytest tests/test_frontend_v06_chat.py tests/test_frontend_v07_chat_experience.py tests/test_frontend_v071_command_palette.py -q`：`9 passed`
- `npm --prefix frontend run build`：通过，仍有既有 Vite large chunk warning。
- 本地服务复测法律交通事故问题：
  - `vector_hits=50`、`keyword_hits=50`、`rrf_hits=50`、`rerank_hits=8`。
  - top selected context 为 `第一千二百一十三条 / 机动车 / 交通事故 / 强制保险 / 商业保险`。
  - answer 可引用 `第一千一百九十条` 和 `第一千二百一十三条` 进行规则适用分析。
- Browser smoke：`http://localhost:8000/#/chat` 确认左上角为 `knowmate知友`，侧边栏为“设置”，右下角身份头像区不存在。

## v0.9

v0.9 是 v0.8 之后的固定 Quick Q&A 主链路版本，聚合 TASK-046 到 TASK-055。目标是把 KnowMate 从“可配置实验型 RAG”收敛为单一、可解释、可验收的 WeKnora-style 快速问答链路：Qdrant dense retrieval + ParadeDB pg_search BM25 + RRF + mandatory rerank + parent-child context。

### Added

- 新增集中化 v0.9 retrieval config：
  - 固定 `retrieval_mode=hybrid`、`vector_engine=qdrant`、`keyword_engine=paradedb_bm25`。
  - 固定向量召回 top50、关键词召回 top50、RRF top30、rerank top8、最终 context 6 段和最多 8000 字符。
  - 仅保留 `rerank_model_id` 作为用户需要绑定的检索模型配置项。
- 新增 ParadeDB BM25 schema 和 repository 边界：
  - Alembic migration 创建 `pg_search` 扩展和 `chunks` BM25 索引。
  - PostgreSQL keyword search 使用 ParadeDB `search_text ||| :query`、`pdb.score(id)` 和 `pdb.snippet(search_text)`。
  - 缺少 ParadeDB/pg_search 或索引不可用时返回中文明确错误。
- 新增固定 parent-child chunk 数据契约：
  - parent chunks 只入库作为回答上下文。
  - child chunks 用于 embedding、Qdrant payload 和 ParadeDB BM25 检索。
  - child payload 补齐 document id、chunk id、parent id、title、context header、chunk type 和 metadata。
- 新增文档处理双写：
  - 处理时清理旧 Qdrant/BM25 索引，再写 PostgreSQL chunks、BM25 child chunks 和 Qdrant child payload。
  - 文档和知识库软删除同步清理 BM25 与向量索引。
- 新增 v0.9 final context / sources / trace 契约：
  - parent_expand 移到 rerank 之后，使用 rerank 选出的 child hits 扩展 parent context。
  - Quick Q&A context_select 按 parent/context 去重、编号并限制数量和字符数。
  - sources 返回 `document_title`、`source_type`、`snippet`、child chunk id、parent chunk id、score、rerank score 和 metadata。
  - retrieval trace 返回 query original/normalized/rewritten、vector/keyword/RRF/rerank hit counts、selected_contexts 和非敏感模型摘要。

### Changed

- Quick Q&A / knowledge-search 公开 schema 不再提供用户可选 `mode`；旧请求体里的 `mode` 会被忽略，实际始终走固定 hybrid 主链路。
- Rerank 不再可选。有候选命中但未配置可用 `Rerank` 模型时，非流式和流式 Quick Q&A 都返回中文硬错误，不静默 fallback。
- Knowledge base 创建和编辑默认固定启用 parent-child 与 rerank。
- 前端设置页改为 v0.9 固定主链路展示，不再提供 retrieval mode 选择、关闭 rerank、关闭 parent-child 或 planned vector backend 列表。
- SourceCard 和 Chat trace 展示 v0.9 sources / retrieval trace，并继续避免 `[object Object]`。
- Docker Compose 现在包含完整后端栈 `postgres / redis / qdrant / api / worker`；`api` 启动时自动执行 `alembic upgrade head`，`worker` 等待 API healthy 后消费任务。
- `scripts/start-dev.ps1` 改为默认启动 Docker 后端栈和本机 Vite，并清理本机 API / Celery 残留，避免 Windows 路径和 Linux 容器路径混跑导致解析失败。

### Not Included

- 不实现登录、RBAC、多租户 workspace、审计日志。
- 不实现 Agent Mode、Wiki Mode、GraphRAG、外部数据源同步或 Web Search provider。
- 不接入 OpenSearch/Elasticsearch/Milvus/Weaviate/Doris/Tencent VectorDB 作为用户可选后端。
- 不接入真实 MinerU/OCR、DocReader、WeKnoraCloud、VLM、ASR。
- 自动化测试不依赖真实外部模型 API key；真实端到端问答仍需要人工配置 QA、Embedding 和 Rerank 模型。

### Verification

- `python -m pytest -q`：`209 passed`
- `ruff check .`：通过
- `python -m compileall app tests`：通过
- `npm --prefix frontend run build`：通过，仍有既有 Vite 大 chunk 提示。
- `alembic upgrade 0016_task032_faq_recommended:head --sql | Select-String -Pattern "pg_search|USING bm25|ix_chunks_paradedb_bm25"`：确认生成 `CREATE EXTENSION IF NOT EXISTS pg_search`、`USING bm25` 和 `ix_chunks_paradedb_bm25`。
- Browser smoke：`http://127.0.0.1:5173/#/settings?section=retrieval` 确认 v0.9 固定主链路展示，旧 retrieval mode / rerank / parent-child 开关 test id 不存在；`http://127.0.0.1:5173/#/chat` 确认页面可渲染且空态不出现 `[object Object]`。
- Docker Desktop 可用后补验通过：
  - `docker compose up -d --build`：`api / worker / postgres / redis / qdrant` 均 healthy，`api` 自动执行在线迁移。
  - 数据库中 `pg_search 0.24.0` 已安装，`ix_chunks_paradedb_bm25` BM25 索引存在。
  - 本地服务 E2E：使用真实 PostgreSQL/ParadeDB 和 Qdrant、进程内 fake Embedding/Chat/Rerank，验证知识库创建、文档上传、同步处理、parent-child chunks、Qdrant point、ParadeDB BM25 hit、knowledge-search 和 quick-answer trace/sources 均通过。验收输出：`vector_hits=1`、`keyword_hits=1`、`rrf_hits=1`、`rerank_hits=1`、`selected_contexts=1`。
  - `scripts/start-dev.ps1`：成功启动 Docker 后端栈和本机 Vite；`celery inspect ping` 只剩 Docker worker，`1 node online`；`/health` 返回 `{"status":"ok"}`，`http://127.0.0.1:5173` 返回 200。

## v0.8

v0.8 是 v0.71 之后的 WeKnora-style Quick Q&A 可解释性、检索质量和管理闭环版本，聚合 TASK-025 到 TASK-045。主线仍保持单租户 Quick Q&A，不进入 Agent/Wiki/RBAC 大范围。

### Added

- 新增 Quick Q&A retrieval diagnostics 后端和前端展示：
  - trace 细化到 rewrite、vector、keyword、RRF、parent_expand、deduplicate、FAQ merge、rerank、answer 等阶段。
  - answer 侧保存 `rendered_context` 和 `prompt_context_summary`，便于复盘回答上下文。
  - 多轮问答增加轻量 history merge，追问会结合最近上下文生成检索输入。
- 新增 rerank 质量控制：
  - rerank passage cleaning、失败降级、阈值降级和 MMR 去冗余。
  - 低置信 rerank 结果会回退到原始排序，避免硬过滤导致无结果。
- 新增 FAQ 导入和管理闭环：
  - FAQ 导入记录 progress、last result、display status 和失败摘要。
  - FAQ 支持字段批量更新，包括启停、推荐状态、标签和 metadata 同步。
  - 检索阶段新增 FAQ merge / boost 独立策略，高置信 FAQ 命中可有限提权。
- 新增 chunk 管理能力：
  - 支持按 chunk id 查询、更新 content/search_text/metadata/is_enabled 和禁用 chunk。
  - 支持 generated questions 手工新增/删除，并同步 search_text 和向量 payload metadata。
  - 前端文档预览可打开 chunk 详情抽屉，编辑 chunk 和 generated questions。
- 新增 chunk debug 和 token-aware validation：
  - chunker preview 展示策略链、被拒绝层级、文档画像、保护块统计和 size distribution。
  - 增加轻量 token 估算和 token limit 生效诊断，覆盖中文、英文和混合文本。
- 新增会话检索与统计：
  - `POST /api/v1/messages/search` 支持按历史问答搜索。
  - `GET /api/v1/messages/chat-history-stats` 返回会话和消息统计。
  - Chat 侧栏展示历史问答搜索入口和可检索消息数。
- 新增模型和向量后端元数据：
  - `GET /api/v1/models/providers` 返回 OpenAI-compatible provider presets。
  - `GET /api/v1/vector-stores/types` 返回 Qdrant 可用状态和 OpenSearch、Elasticsearch、Milvus、Weaviate、Doris、Tencent VectorDB 等 planned provider metadata。
  - 引入 composite retriever 接口和 retriever fan-out diagnostics。
  - 新增 OpenSearch/Elasticsearch sparse/BM25 后端 MVP，当前以 fake/test-client 与配置边界验证为主。
- 新增运行状态真实化和附件上下文：
  - `/api/v1/runtime-status` 增强 database、local storage、vector runtime、model_configs、vector_stores、storage_providers、parser engines 和修复建议。
  - Quick Q&A 支持临时文本附件上下文，附件只进入本轮 prompt，不写入知识库、不写入 Qdrant、不作为 sources 返回。

### Fixed

- 修复 Alembic revision id 超过 PostgreSQL 默认 `alembic_version.version_num` 长度导致 `alembic upgrade head` 失败的问题，TASK-032 migration revision 缩短为 `0016_task032_faq_recommended`。
- 修复 `scripts/start-dev.ps1` 对 `docker compose` 和 `alembic` 等原生命令非零退出不敏感的问题；现在会检查 `$LASTEXITCODE` 并停止启动流程。

### Changed

- Quick Q&A source、trace、last-request state 和 rendered context 更完整地暴露检索依据，但仍不回显 API Key 等敏感信息。
- Settings 页面从静态占位进一步转为真实运行状态和 provider 能力展示。
- VectorStore 管理仍只允许创建当前可用 provider；planned provider 返回明确中文错误，不做静默 fallback。

### Not Included

- 不实现完整登录、RBAC、多租户 workspace、审计日志。
- 不实现 Agent Mode、MCP 工具、Wiki Mode、GraphRAG 或外部数据源同步。
- 不接入生产级 OpenSearch/Elasticsearch 集群、Milvus、Weaviate、Doris、Tencent VectorDB 或对象存储 provider。
- 不接入真实 MinerU/OCR、DocReader、WeKnoraCloud、VLM、ASR。

### Verification

- `python -m pytest -q`：`184 passed`
- `ruff check app tests`：通过
- `python -m compileall app tests alembic`：通过
- `npm --prefix frontend run build`：通过，仍有 Vite 大 chunk 提示。
- `python -m pytest tests/test_dev_start_script.py tests/test_v07_chat_mentioned_items.py tests/test_v06_quick_answer_stream.py -q`：`12 passed`
- `ruff check alembic app tests`：通过
- 本地启动烟测：`scripts/start-dev.ps1` 完成后 PostgreSQL、Redis、Qdrant healthy，API `/health` 返回 `{"status":"ok"}`，Alembic current 为 `0016_task032_faq_recommended (head)`，Vite 工作台 `http://127.0.0.1:5173/#/chat` 显示“后端已连接”。

## v0.71

v0.71 是 v0.7 WeKnora P0 对齐之后的 Quick Q&A 操作闭环与可观测性版本，聚合 TASK-020 到 TASK-024，并补齐软删除后同文件重新上传的稳定性问题。本版本仍不进入 Agent/Wiki/RBAC 大范围，继续保持单租户 Quick Q&A 主线。

### Added

- 新增上传队列和多文件进度：
  - 文档上传组件支持一次选择多个文件。
  - 文档页逐文件展示 pending / uploading / queued / processing / completed / failed 状态。
  - 上传成功后展示 document id 和匹配到的 task id，并区分上传失败、解析失败和部分成功摘要。
- 新增文档生命周期操作：
  - 新增文档原文件下载 API 和前端入口。
  - 新增 queued/processing 文档取消解析，取消后同步任务状态和处理 timeline。
  - 新增文档移动到其他兼容知识库，校验 KB 类型和 Embedding 模型兼容，并同步 chunk 与 Qdrant payload 归属。
- 新增会话生成生命周期：
  - Quick Answer stream 支持 `/api/v1/chat-sessions/{session_id}/stop` 停止生成。
  - 停止后保存 partial assistant message 为 cancelled。
  - 空白或占位会话标题在首问后自动生成可读标题。
  - 会话保存 `settings_json.last_request_state`，记录 scope、检索命中、模型摘要、耗时和状态。
- 新增阶段化 retrieval trace 和运行状态：
  - retrieval trace 新增 rewrite / search / rerank / answer 阶段列表，包含状态、耗时和输出摘要。
  - 新增 `GET /api/v1/runtime-status`，返回 database、local storage、vector store、parser registry 和 system 状态。
  - 设置页使用 runtime status 展示真实 parser/storage/system 状态。
- 新增 Command Palette 最小版：
  - 支持按钮和 Ctrl/Meta+K 打开。
  - 支持按关键字过滤并跳转快速问答、知识库、文档管理、FAQ 管理、模型配置、检索设置、解析器状态和存储状态。

### Fixed

- 修复同一文件曾上传、解析中止、软删除记录后再次上传会复用 deterministic document id，导致 `knowledges.id` 主键冲突并在前端显示 `上传失败：Internal Server Error` 的问题。
- 同一知识库内活跃重复文件现在返回 `409 Conflict` 和中文错误 `该文件已上传，请勿重复上传。`；已软删除的同 hash 文件允许重新上传并生成新的 document id。

### Changed

- 文档页上传结果从单次操作提示扩展为队列级状态，便于定位部分成功和单文件失败。
- Chat trace 面板从原始 trace JSON 展示增强为阶段化可读状态。
- 设置中心 parser/storage 状态不再依赖静态占位，优先展示后端 runtime status。

### Not Included

- 不实现完整登录、RBAC、多租户 workspace、审计日志。
- 不实现 Agent Mode、MCP 工具、Wiki Mode、GraphRAG 或外部数据源同步。
- 不实现附件上下文、文件夹上传、FAQ import progress、FAQ last import result 或字段批量更新；这些保留为 v0.71 P1 / v0.72 候选。
- 不接入真实 MinerU/OCR、对象存储 provider、Web Search provider 或完整 BM25 引擎。

### Verification

- `python -m pytest tests/test_frontend_v071_upload_queue.py -q`：`1 passed`
- `python -m pytest tests/test_v071_document_lifecycle.py tests/test_frontend_v071_document_lifecycle.py -q`：`5 passed`
- `python -m pytest tests/test_v071_chat_generation_lifecycle.py tests/test_frontend_v071_chat_generation_lifecycle.py -q`：`4 passed`
- `python -m pytest tests/test_v071_observability_status.py tests/test_frontend_v071_observability_status.py -q`：`3 passed`
- `python -m pytest tests/test_frontend_v071_command_palette.py -q`：`1 passed`
- `python -m pytest tests/test_v05_document_management.py::test_deleted_duplicate_file_can_be_uploaded_again tests/test_v05_document_management.py::test_active_duplicate_file_upload_returns_chinese_error -q`：`2 passed`
- `python -m pytest tests/test_v05_document_management.py tests/test_v021_crud_endpoints.py tests/test_v071_document_lifecycle.py -q`：`13 passed`
- `ruff check app\api\v1\documents.py app\db\repositories\document.py app\services\document.py tests\test_v05_document_management.py`：通过
- `python -m compileall app tests`：通过
- `npm --prefix frontend run build`：通过，仍有 Vite 大 chunk 提示。

## v0.7

v0.7 是在 v0.61 知识管理补强基础上的 WeKnora P0 对齐版本，聚合 TASK-010 到 TASK-019。本版本仍不进入 Agent/Wiki/RBAC 大范围，而是把 Quick Q&A 主链路周边的知识库平台化、范围检索、处理可观测性和 FAQ 高级索引补到更接近 WeKnora 的可用状态。

### Added

- 新增知识库 capabilities 和 pin 后端基础：
  - 新增 `knowledge_base_pins` 表和 Alembic migration `0011_v07_kb_pins`。
  - 知识库读取和列表返回 `capabilities`、`is_pinned`、`pinned_at`。
  - 新增 `PUT /api/v1/knowledge-bases/{kb_id}/pin`，列表按置顶状态排序。
- 新增知识库列表 pin / capabilities 前端展示：
  - 列表支持 pin/unpin。
  - 展示能力标签组，Wiki / Graph 等未启用能力保持禁用占位。
- 新增 WeKnora-like KB 详情一体化页面骨架：
  - 新增 `/#/knowledge-bases/:kbId`。
  - 详情页收敛概览、文档/FAQ 工作流、设置、任务/状态入口。
  - 旧文档和 FAQ 路由继续保留。
- 新增创建后 KB 设置面板：
  - 可编辑基础信息、QA / Embedding 模型、parser rules、chunking config、indexing strategy 和 vector store。
  - 保存复用 `PUT /api/v1/knowledge-bases/{kb_id}`，成功后提示需要重处理或重建索引。
- 新增多知识库和文件范围检索：
  - `knowledge-search` 和 `quick-answer` 支持 `knowledge_base_ids` 与 `knowledge_ids`。
  - 支持单 KB、多 KB、KB + 文件范围 fan-out 检索后合并去重。
  - 校验跨 KB Embedding 模型一致性，避免不同向量维度混用。
  - sources 新增 `knowledge_base_name`。
- 新增 Chat mention 范围选择体验：
  - Chat 工作台支持显式 KB/file scope 选择和 mention chips。
  - 发送和检索调试会提交 `knowledge_base_ids`、`knowledge_ids` 和 `mentioned_items`。
  - 用户消息持久化并展示 mentioned items。
- 新增文档处理 spans/timeline：
  - 新增 `knowledge_processing_spans` 表和 Alembic migration `0012_v07_processing_spans`。
  - 新增 `GET /api/v1/documents/{document_id}/spans`。
  - 文档处理记录 parse、chunk、embed、upsert、finalize 五阶段状态、耗时、错误和 downstream cancelled。
  - 旧文档无 spans 时返回 attempt `0` 安全占位。
  - 前端文档列表、预览抽屉和处理时间线抽屉展示阶段状态。
- 新增 FAQ similar questions 和索引模式：
  - 新增 Alembic migration `0013_v07_faq_similar_indexing`。
  - `KnowledgeBase` 支持 `faq_config.index_mode` 和 `faq_config.question_index_mode`。
  - `FAQEntry` 支持 `similar_questions`。
  - FAQ 导入导出新增 `similar_questions` 列。
  - FAQ 索引按 `question_only / question_answer` 与 `combined / separate` 生成 chunk、search_text 和 Qdrant payload。
  - metadata 标记 `standard_question`、`similar_questions`、`matched_question`、`question_role` 和 `index_mode`。
  - FAQ 管理页展示相似问法，编辑弹窗可输入相似问法，检索测试展示命中问法。

### Changed

- 知识库创建和列表入口默认进入 KB detail，降低文档/FAQ 页面割裂感。
- 多 scope 检索仍保持旧单 KB 请求兼容；未传新 scope 时沿用原 `knowledge_base_id` 行为。
- SourceCard 在多 KB 检索场景下显示真实知识库来源。
- FAQ 相似问法会去空、去重，并过滤与标准问题相同的问法。

### Not Included

- 不实现完整登录、RBAC、多租户 workspace、审计日志。
- 不实现 Agent Mode、MCP 工具、Wiki Mode、GraphRAG 或外部数据源同步。
- 不实现停止生成、自动标题、附件上下文、文件夹上传、文档下载、取消解析和文档移动；其中停止生成、自动标题、文档下载、取消解析和文档移动已在 v0.71 落地，附件上下文和文件夹上传继续后续规划。
- 不接入真实 MinerU/OCR、对象存储 provider、Web Search provider 或完整 BM25 引擎。

### Verification

- `python -m pytest tests/test_v07_kb_capabilities_pin.py -q`：`4 passed`
- `python -m pytest tests/test_frontend_v07_kb_pin_capabilities.py -q`：`1 passed`
- `python -m pytest tests/test_frontend_v07_kb_detail_shell.py -q`：`1 passed`
- `python -m pytest tests/test_frontend_v07_kb_settings_panel.py -q`：`1 passed`
- `python -m pytest tests/test_v07_kb_settings_update.py -q`：`2 passed`
- `python -m pytest tests/test_v07_multi_scope_retrieval.py -q`：`5 passed`
- `python -m pytest tests/test_frontend_v07_chat_mentions.py -q`：`1 passed`
- `python -m pytest tests/test_v07_chat_mentioned_items.py -q`：`1 passed`
- `python -m pytest tests/test_v07_processing_spans.py -q`：`4 passed`
- `python -m pytest tests/test_frontend_v07_processing_timeline.py -q`：`1 passed`
- `python -m pytest tests/test_v07_faq_similar_indexing.py -q`：`2 passed`
- `python -m pytest tests/test_frontend_v07_faq_similar_indexing.py -q`：`1 passed`
- `python -m pytest -q`：`125 passed`
- `python -m pytest (rg --files tests | rg 'test_frontend_.*\\.py$') -q`：`24 passed`
- `ruff check .`：通过
- `python -m compileall app tests`：通过
- `npm --prefix frontend run build`：通过，仍有 Vite 大 chunk 提示。
- 浏览器 stub 验证：文档处理时间线可展示 failed/cancelled 阶段和错误文本；FAQ 页面可展示相似问法与检索命中问法。

## v0.61

v0.61 是在 v0.6 会话化 Quick Q&A 基础上的 WeKnora 对齐补强版本，聚合 TASK-001 到 TASK-009。本版本不扩大到 Agent/Wiki/RBAC 主线，而是把知识库管理、FAQ、文档预览、批处理反馈、设置中心和会话侧栏体验补到更接近 WeKnora 的产品化状态。

### Added

- 新增知识库级标签体系：
  - 新增 `knowledge_tags` 表和 Alembic migration `0010_v07_tags`。
  - 新增 `/api/v1/knowledge-bases/{kb_id}/tags` 标签 CRUD。
  - 文档、FAQ、chunks 和 Qdrant payload 记录 `tag_id`。
  - 文档和 FAQ 列表支持按标签筛选，支持批量分配/清除标签。
- 新增文档预览能力：
  - 新增 `/api/v1/documents/{document_id}/preview`。
  - 从已解析 chunks 生成文档摘要、正文预览和 chunk outline。
  - 前端文档页把原 chunk drawer 升级为预览抽屉，支持从 outline 跳转 chunk 内容。
- 新增 FAQ CSV/XLSX 导入导出：
  - 新增 FAQ 导入服务，支持 append/replace、逐行失败摘要、metadata JSON、enabled、tag_id。
  - 新增 CSV/XLSX 导出。
  - 前端 FAQ 页新增导入弹窗、导入结果卡片、CSV/XLSX 导出按钮。
- 新增 FAQ 检索测试面板：
  - 前端复用 `/api/v1/knowledge-search`，限定当前知识库执行 FAQ 搜索测试。
- 新增批处理进度和部分失败摘要：
  - 文档批量删除/重处理响应新增 `requested`、`succeeded`、`failed`、`failures` 和 `task_ids`。
  - 任务列表和详情新增 `batch_summary`，汇总同知识库同任务类型的 queued/processing/completed/failed 数量和失败原因。
  - 文档页新增批处理进度面板、失败原因展示和失败任务重试入口。
- 新增 WeKnora-like 设置中心外壳：
  - 新增 `/#/settings`，集中组织模型、VectorStore、检索、解析器和存储状态。
  - 旧 `/#/settings/models`、`/#/settings/vector-stores`、`/#/settings/retrieval` 保留为重定向入口。
  - 解析器区展示 `Builtin Parser`、`Local Parser Registry`、`MinerU OCR` 状态。
  - 存储区展示 `Local Storage` 以及 MinIO、S3、OSS、COS、OBS 等暂未启用 provider 占位。
- 新增会话体验增强：
  - `GET /api/v1/chat-sessions?keyword=` 支持按会话标题和消息内容搜索。
  - 新增 `POST /api/v1/chat-sessions/batch-delete` 批量软删除会话，并返回部分失败摘要。
  - 新增 `GET /api/v1/chat-sessions/recommended-questions`，从 FAQ 和 chunk `generated_questions` 生成推荐问题。
  - 前端 Chat 侧边栏新增搜索框、批量选择和批量删除；空会话区展示可点击推荐问题。

### Changed

- 前端侧边栏把分散的模型、VectorStore、检索配置入口收敛为“设置中心”。
- 文档和 FAQ 页面增加标签筛选/分配后的操作状态可见性。
- FAQ 导入错误、批处理失败、会话批量删除失败均以中文可读摘要展示，不渲染原始对象。
- 推荐问题第一阶段不调用 LLM，优先使用 FAQ 问题和已有 chunk metadata，避免引入新的外部模型依赖。

### Not Included

- 不实现完整 RBAC、登录、多 workspace、审计日志。
- 不实现 Agent Mode、Wiki Mode、MCP、IM、小程序或外部数据源同步。
- 不接入真实 MinerU/OCR、MinIO/S3/OSS 等 provider；v0.61 只做可见状态和占位。
- 不引入新的 BM25/GraphRAG/多维索引引擎。

### Verification

- `python -m pytest tests/test_v07_tags.py -q`：`4 passed`
- `python -m pytest tests/test_v07_document_preview.py -q`：`3 passed`
- `python -m pytest tests/test_v07_faq_import_export.py -q`：`3 passed`
- `python -m pytest tests/test_v07_batch_progress.py tests/test_frontend_v07_batch_progress.py -q`：`3 passed`
- `python -m pytest tests/test_frontend_v07_settings_shell.py -q`：`1 passed`
- `python -m pytest tests/test_v07_chat_experience.py tests/test_frontend_v07_chat_experience.py -q`：`4 passed`
- `python -m pytest tests/test_v07_chat_experience.py tests/test_v06_chat_sessions.py tests/test_v06_quick_answer_stream.py -q`：`9 passed`
- `python -m pytest (rg --files tests | rg 'test_frontend_.*\\.py$') -q`：`18 passed`
- `ruff check .`：通过
- `python -m compileall app tests`：通过
- `npm --prefix frontend run build`：通过，仍有 Vite 大 chunk 提示。

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
