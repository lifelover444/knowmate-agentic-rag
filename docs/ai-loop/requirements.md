# AI Task Board

长期目标：以 Tencent/WeKnora 为产品和架构参照，把 `knowmate 知友` 做成 FastAPI 技术栈下的近似复现。推进方式为单任务循环：每次只选一个可测试的小任务，对照 WeKnora 源码实现，完成测试后再进入下一项。

参考基线：
- knowmate 当前主线：v0.61 已完成 TASK-001 到 TASK-009，基于 v0.6 会话化 Quick Q&A 补齐标签、文档预览、FAQ 导入导出、批处理反馈、设置中心和会话体验增强。
- WeKnora 参考源码：`D:/myproject/_references/WeKnora`，commit `e352721`，仅作为只读参考。
- 差距文档：`docs/weknora-visible-gap-analysis-v0.6-v0.7.zh-CN.md`。

## Active
None

## Queue

## Parking Lot
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
