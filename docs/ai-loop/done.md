# AI Done Log

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

## Entry Template
### YYYY-MM-DD | TASK-000 | Short summary
- summary: What was delivered.
- files: path/to/file
- follow_ups: none
