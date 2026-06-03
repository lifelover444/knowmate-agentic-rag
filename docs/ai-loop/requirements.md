# AI Task Board

长期目标：以 Tencent/WeKnora 为产品和架构参照，把 `knowmate 知友` 做成 FastAPI 技术栈下的近似复现。推进方式为单任务循环：每次只选一个可测试的小任务，对照 WeKnora 源码实现，完成测试后再进入下一项。

参考基线：
- knowmate 当前主线：v0.8 已完成 TASK-025 到 TASK-045，基于 v0.71 操作闭环继续补齐 retrieval diagnostics、rendered context、history merge、rerank cleaning/MMR、FAQ import progress、FAQ 字段批量更新、FAQ boost、chunk 管理、generated questions、chunk debug、token-aware validation、message search、model providers、vector-store types、composite retriever、OpenSearch sparse MVP、runtime status 真实化和临时文本附件上下文。
- WeKnora 参考源码：`D:/myproject/_references/WeKnora`，`VERSION=0.6.0`，commit `e352721`，迁移已到 `000057_models_display_name`，仅作为只读参考。
- 差距文档：`docs/weknora-full-gap-analysis-2026-06-02.zh-CN.md`；Quick Q&A 任务提示词见 `docs/quick-qa-weknora-task-prompts.zh-CN.md`。v0.8 Quick Q&A 任务包已完成，当前剩余差距集中在 Auth/RBAC-lite、per-user 偏好、文件夹上传、Web Search provider、Markdown/Mermaid 安全渲染、高级解析、Agent/Wiki/DataSource 等后续范围。

## Active
暂无。TASK-025 到 TASK-045 已全部完成并通过全量验收。

## Queue
暂无。

## Parking Lot
- v0.9 候选：Auth/RBAC-lite、用户、tenant member、KB ownership、审计日志和权限感知 UI。
- v0.9 候选：per-user pin / favorites 预留，保持单租户默认 principal。
- v0.9 候选：文件夹上传、Web Search provider 设置占位、Mermaid 渲染和更完整 Markdown 安全渲染。
- Agent Mode MVP：Agent 列表、Agent 编辑器、knowledge-search 工具、流式工具调用展示。
- Wiki Mode MVP：Wiki KB 类型、从 chunks 生成只读 Markdown wiki pages、Wiki browser、基础互链。
- RBAC-lite：登录、用户、workspace/tenant shell、Owner/Admin/Viewer、KB ownership、审计日志。
- 高级解析：OCR、MinerU、图片/VLM、PPT、ASR。
- 外部数据源同步：Feishu / Notion / Yuque。
- CLI / MCP server / Chrome Extension / WeChat Mini Program / IM channels。
- Langfuse 或等价可观测性。

## Rules
- Keep zero or one task in `## Active`.
- Add new requests to `## Queue` unless the user explicitly defers them.
- Split large requests into the smallest independently shippable task.
- Before production code changes, confirm the selected `TASK-*` with the user.
- For each task: compare WeKnora source first, write/update focused tests, implement, run smallest relevant verification, then broaden.
- When a task finishes, append an entry to `done.md` and remove it from `## Active`.
