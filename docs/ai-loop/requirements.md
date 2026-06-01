# AI Task Board

长期目标：以 Tencent/WeKnora 为产品和架构参照，把 `knowmate 知友` 做成 FastAPI 技术栈下的近似复现。推进方式为单任务循环：每次只选一个可测试的小任务，对照 WeKnora 源码实现，完成测试后再进入下一项。

参考基线：
- knowmate 当前主线：v0.7 已完成 TASK-010 到 TASK-019，基于 v0.61 知识管理补强继续补齐 KB capabilities / pin、KB 详情一体化设置、多知识库/文件范围检索、Chat mention、文档处理 timeline、FAQ 相似问法和 FAQ 索引模式。
- WeKnora 参考源码：`D:/myproject/_references/WeKnora`，commit `e352721`，仅作为只读参考。
- 差距文档：`docs/weknora-local-comparison-v0.7-roadmap.zh-CN.md`；v0.7 P0 已完成，后续按 Parking Lot 规划 v0.71。

## Active
None

## Queue

## Parking Lot
- v0.71 候选：上传队列和多文件进度、停止生成、会话自动标题、文档下载、取消解析、文档移动到其他 KB、retrieval trace 阶段增强、Command Palette、真实 parser/storage status API。
- v0.71 候选：Auth/RBAC-lite、附件上下文、文件夹上传、Web Search provider 设置占位、Mermaid 渲染和更完整 Markdown 安全渲染。
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
