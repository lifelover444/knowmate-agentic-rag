# AI Done Log

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
