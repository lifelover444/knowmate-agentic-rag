# knowmate 与本地 WeKnora 复刻差距对比及 v0.71 归档

日期：2026-06-02

对比范围：

- knowmate：`D:\myproject\knowmate-agentic-rag`
- WeKnora 参考源码：`D:\myproject\_references\WeKnora`
- WeKnora 版本：`VERSION=0.6.0`，commit `e352721`，迁移到 `000057_models_display_name`

本文件承接 `docs/weknora-local-comparison-v0.7-roadmap.zh-CN.md`。v0.7 已完成知识库平台化 P0；v0.71 继续聚焦 Quick Q&A 操作闭环与可观测性，不进入完整 Agent/Wiki/RBAC 平台范围。

## 当前结论

knowmate v0.71 已完成 v0.7 后最靠近 WeKnora Quick Q&A 日常使用体验的 P0 缺口：

1. 上传队列和多文件进度。
2. 文档下载、取消解析和移动到其他知识库。
3. 停止生成、自动标题和 last-request state。
4. Retrieval trace 阶段化，以及真实 parser/storage/system status API。
5. Command Palette 最小版。

同时，v0.71 修复了一个上传稳定性问题：同一文件曾上传并软删除后再次上传，不再复用已删除记录的 deterministic document id，避免触发 `knowledges.id` 主键冲突；活跃重复文件返回中文 409 错误。

## P0 完成项

### TASK-020 上传队列和多文件进度

- 前端文档上传支持一次选择多个文件。
- 文档页展示本地上传队列，逐文件区分 pending / uploading / queued / processing / completed / failed。
- 上传成功后展示 document id 和 task id。
- 页面明确区分上传失败、解析失败和部分成功。

### TASK-021 文档下载、取消解析和移动

- 新增原文件下载接口和前端操作。
- 新增 queued / processing 文档取消解析。
- 取消解析会同步任务状态和 processing spans/timeline。
- 新增文档移动到兼容知识库，校验 KB 类型与 Embedding 模型一致性。
- 移动文档会同步 PostgreSQL chunks 和 Qdrant payload 的知识库归属。

### TASK-022 停止生成、自动标题和 last-request state

- Quick Answer stream 增加进程内 stop registry。
- 新增 `/api/v1/chat-sessions/{session_id}/stop`。
- 流式生成在 token 边界响应停止，并保存 cancelled partial assistant message。
- 首问后为默认标题会话生成可读标题。
- 会话 `settings_json.last_request_state` 保存最近请求的 scope、命中数、模型摘要、耗时和状态。

### TASK-023 Retrieval trace 阶段化和真实运行状态

- retrieval trace 新增 rewrite / search / rerank / answer 阶段列表。
- 阶段记录 status、duration 和输出摘要。
- 新增 `/api/v1/runtime-status`。
- runtime status 返回 database、local storage、vector store、parser registry 和 system 概览。
- 设置页从 runtime status 加载 parser/storage/system 状态。

### TASK-024 Command Palette 最小版

- 新增全局 `CommandPalette`。
- 支持按钮和 Ctrl/Meta+K 打开。
- 支持按关键字过滤快速跳转 Chat、知识库、文档管理、FAQ、模型配置、检索设置、解析器状态和存储状态。

## v0.71 Bugfix

### 软删除后同文件重新上传

问题场景：

1. 用户上传 `中华人民共和国刑法_20201226.pdf`。
2. 处理过程中中止或失败。
3. 用户删除首次上传记录。
4. 再次上传同一文件时，服务端按 `knowledge_base_id + file_hash` 生成同一个 deterministic document id。
5. 旧软删除记录仍占用 `knowledges.id` 主键，导致数据库唯一约束冲突，前端显示 `上传失败：Internal Server Error`。

修复后行为：

- 上传前按 `knowledge_base_id + file_hash` 查询活跃重复文件。
- 如果存在活跃重复文件，返回 `409 Conflict` 和中文错误 `该文件已上传，请勿重复上传。`。
- 如果只存在软删除旧记录，生成新的 UUID document id，允许重新上传。
- 相关测试覆盖活跃重复和软删除后重新上传两种路径。

## 与 WeKnora 差距的当前状态

v0.71 后，knowmate 的 Quick Q&A 主链路已经覆盖：

- 模型配置与知识库模型绑定。
- 文档/FAQ 知识库。
- 文档上传、解析、切分、embedding、Qdrant 写入。
- 文档预览、处理 timeline、下载、取消解析、移动。
- FAQ 导入导出、相似问法和 FAQ 索引模式。
- 多知识库 / 文件范围检索和 Chat mention。
- 会话化流式回答、停止生成、自动标题、sources 和阶段化 trace。
- 运行状态 API 和设置页状态展示。
- Command Palette 基础导航。

仍未复刻或仅占位的 WeKnora 平台能力：

- 登录、Tenant、RBAC、成员、邀请、审计日志。
- per-user pin、favorites、user preferences。
- Agent Mode、MCP service、skills、工具审批和工具调用可视化。
- Wiki Mode、GraphRAG、知识图谱 lint / auto-fix。
- DataSource 同步、IM、多端入口、CLI/MCP server。
- Web Search provider。
- OCR / MinerU / VLM / ASR 和对象存储 provider。
- 多 vector store fan-out、真实 sparse/BM25 后端和更完整 evaluation。

## 后续规划

### v0.71 P1 / P2

- FAQ import progress、last import result 和字段批量更新。
- 附件上下文 MVP：先支持文本类附件作为本轮 prompt 临时上下文。
- per-user pin / favorites 预留：保持单租户默认 principal，但为后续用户体系留边界。

### v0.72 候选

- Auth/RBAC-lite、用户、tenant member、KB ownership、审计日志和权限感知 UI。
- 文件夹上传。
- Web Search provider 设置占位。
- Mermaid 渲染和更完整 Markdown 安全渲染。

### v0.8+ 候选

- Agent Mode MVP。
- Wiki Mode MVP。
- 高级解析/OCR/MinerU。
- 外部数据源同步。
- CLI / MCP server / Chrome Extension / IM channels。
- Langfuse 或等价可观测性。

## 验证记录

v0.71 P0 和上传 bugfix 已运行的关键验证：

- `python -m pytest tests/test_frontend_v071_upload_queue.py -q` -> 1 passed
- `python -m pytest tests/test_v071_document_lifecycle.py tests/test_frontend_v071_document_lifecycle.py -q` -> 5 passed
- `python -m pytest tests/test_v071_chat_generation_lifecycle.py tests/test_frontend_v071_chat_generation_lifecycle.py -q` -> 4 passed
- `python -m pytest tests/test_v071_observability_status.py tests/test_frontend_v071_observability_status.py -q` -> 3 passed
- `python -m pytest tests/test_frontend_v071_command_palette.py -q` -> 1 passed
- `python -m pytest tests/test_v05_document_management.py::test_deleted_duplicate_file_can_be_uploaded_again tests/test_v05_document_management.py::test_active_duplicate_file_upload_returns_chinese_error -q` -> 2 passed
- `python -m pytest tests/test_v05_document_management.py tests/test_v021_crud_endpoints.py tests/test_v071_document_lifecycle.py -q` -> 13 passed
- `ruff check app\api\v1\documents.py app\db\repositories\document.py app\services\document.py tests\test_v05_document_management.py` -> passed
- `python -m compileall app tests` -> passed
- `npm --prefix frontend run build` -> passed with existing Vite large chunk warning
