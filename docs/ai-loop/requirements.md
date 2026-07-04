# AI Task Board

长期目标：以 Tencent/WeKnora 为产品和架构参照，把 `knowmate 知友` 做成 FastAPI 技术栈下的近似复现。本文只保留当前轻量路线板；历史逐任务完成日志已归档到 `docs/archive/ai-loop-done-2026-07-04.md`。

参考基线：
- knowmate 当前主线：v1.0 已在 v0.9 固定 Quick Q&A 主链路、v0.91 召回/Chat 体验修复和 v0.92 MinerU 解析能力基础上补齐 RAGas 知识库级评测闭环。当前能力包括黄金评测集、评测运行、五项 RAGas 指标、baseline/current 对比、逐题 source 诊断、前端评测页面，以及法律知识库 50 题黄金集 0.88+ 复测验收。主链路仍固定为 Qdrant dense retrieval + ParadeDB pg_search BM25 + RRF + mandatory rerank + parent-child context，不向用户暴露 retrieval mode、关闭 rerank、关闭 parent-child 或 planned vector backends。
- WeKnora 参考源码：`D:/myproject/_references/WeKnora`，`VERSION=0.6.0`，commit `e352721`，迁移已到 `000057_models_display_name`，仅作为只读参考。
- 参考文档：`docs/v1.0.md`、`docs/quick-answer-weknora-aligned-chain-2026-06-10.zh-CN.md`、`docs/v0.9.md`、`docs/weknora-full-gap-analysis-2026-06-02.zh-CN.md`。
- 当前剩余差距集中在 Auth/RBAC-lite、per-user 偏好、文件夹上传、Web Search provider、Markdown/Mermaid 安全渲染、离线/本地解析能力、人工基准集导入、评测取消/成本控制、Agent/Wiki/DataSource 等后续范围。

## Active

## Queue

## Parking Lot
- 后续候选：Auth/RBAC-lite、用户、tenant member、KB ownership、审计日志和权限感知 UI。
- 后续候选：per-user pin / favorites 预留，保持单租户默认 principal。
- 后续候选：文件夹上传、Web Search provider 设置占位、Mermaid 渲染和更完整 Markdown 安全渲染。
- Agent Mode MVP：Agent 列表、Agent 编辑器、knowledge-search 工具、流式工具调用展示。
- Wiki Mode MVP：Wiki KB 类型、从 chunks 生成只读 Markdown wiki pages、Wiki browser、基础互链。
- RBAC-lite：登录、用户、workspace/tenant shell、Owner/Admin/Viewer、KB ownership、审计日志。
- 高级解析剩余项：离线 MinerU、本地 OCR/VLM/ASR、Office 超 200 页自动拆分或 Office 转 PDF 后分片。
- RAG 评测增强：人工基准集导入、评测取消、成本预算、更多 retrieval 指标 MRR/nDCG、线上定时回归和 Langfuse/Phoenix 类观测集成；v1.0 的 RAGas 自动评测闭环已完成。
- 外部数据源同步：Feishu / Notion / Yuque。
- CLI / MCP server / Chrome Extension / WeChat Mini Program / IM channels。
- Langfuse 或等价可观测性。

## Rules
- Keep zero or one task in `## Active`.
- Add new requests to `## Queue` unless the user explicitly defers them.
- Split large requests into the smallest independently shippable task.
- Before production code changes, confirm the selected `TASK-*` with the user.
- For each task: compare WeKnora source first, write/update focused tests, implement, run smallest relevant verification, then broaden.
- Local runtime convention: use `scripts/start-dev.ps1` for the smart Docker backend stack and local Vite; force rebuild only with `scripts/start-dev.ps1 -Rebuild` or `rebuild-dev.bat`; do not mix local `uvicorn` / `celery` with Docker `api` / `worker`.
- When a task finishes, remove it from `## Active` and update the relevant durable docs: `README.md`, `CHANGELOG.md`, `docs/v*.md`, or this task board.
