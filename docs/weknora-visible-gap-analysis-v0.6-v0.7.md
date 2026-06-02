# knowmate vs Tencent/WeKnora visible feature gap analysis

Date: 2026-05-30

Scope: non-click analysis based on Tencent/WeKnora public README, changelog, DeepWiki source index, and the local knowmate README / CHANGELOG / frontend routes. The first draft used the v0.5 baseline; the baseline was updated to knowmate v0.61 on 2026-05-31 and supplemented with knowmate v0.7 P0 completion status on 2026-06-01. This is not a live UI test report because Chrome automation is blocked by policy on the WeKnora production domain.

2026-06-02 update: the primary comparison reference is now the local `D:\myproject\_references\WeKnora` checkout, with `VERSION=0.6.0`, commit `e352721`, and migrations through `000057_models_display_name`. The current v0.71 completion archive is documented in `docs/weknora-local-comparison-v0.71-roadmap.zh-CN.md`; this file remains an archive of the v0.6-v0.7 visible-gap baseline.

Primary sources:

- Tencent/WeKnora GitHub: https://github.com/Tencent/WeKnora
- Tencent/WeKnora README feature overview: https://github.com/Tencent/WeKnora
- Tencent/WeKnora CHANGELOG: https://raw.githubusercontent.com/Tencent/WeKnora/main/CHANGELOG.md
- DeepWiki frontend/navigation/knowledge/chat/settings pages:
  - https://deepwiki.com/Tencent/WeKnora/7.1-navigation-and-menu-system
  - https://deepwiki.com/Tencent/WeKnora/7.2-knowledge-base-interface
  - https://deepwiki.com/Tencent/WeKnora/7.3-chat-interface-and-agent-display
  - https://deepwiki.com/Tencent/WeKnora/7.4-settings-and-configuration-interface

## Executive Summary

knowmate v0.7 covers the core Quick Q&A foundation plus conversation-ready chat, tags, document preview, FAQ import/export, batch feedback, settings-center shell, KB capabilities / pin, integrated KB detail settings, multi-scope retrieval, Chat mention, document-processing timeline, FAQ similar questions, and FAQ indexing modes. The largest remaining gaps are no longer basic RAG ingestion, but WeKnora's broader Agent, Wiki, workspace/RBAC, advanced parsing, external import, multi-client, and enterprise observability surfaces.

## v0.7 Update

As of 2026-06-01, TASK-010 through TASK-019 are consolidated as knowmate `v0.7`. v0.7 still avoids the larger Agent/Wiki/RBAC scope and delivers the original v0.7 P0 Quick Q&A platformization items:

- KB capabilities and pinning.
- Integrated KB detail page and post-create settings editing.
- Multi-KB / file-scope retrieval and Chat mention scope.
- Document-processing parse/chunk/embed/upsert/finalize timeline.
- FAQ similar questions, FAQ indexing modes, and matched-question display.

Therefore, the original v0.7 P0 recommendations in this document are now delivered. Upload queue, stop generation, automatic title generation, document download/cancel/move, retrieval trace deepening, command palette, and real parser/storage status are delivered in v0.71; attachment context and RBAC-lite remain later candidates.

## v0.71 Completion Update

After comparing against the local WeKnora 0.6.0 source, the largest remaining gaps have shifted from the Quick Q&A core flow to platform-stage capabilities: Tenant RBAC, per-user pinning, user preferences/favorites, CLI/MCP server, DataSource, IM, Wiki, Web Search, multi-vector-store fan-out, object storage, attachments, and operations visibility. To keep knowmate's v1 Quick Q&A path focused, v0.71 delivered:

1. Upload queue and per-file progress.
2. Document download, cancel parsing, and move to another KB.
3. Stop generation, automatic session titles, and last-request state.
4. Stage-level retrieval trace plus real parser/storage/system status APIs.
5. A minimal Command Palette.

v0.71 also fixed the soft-delete re-upload conflict that could surface as an Internal Server Error after uploading, interrupting, deleting, and re-uploading the same file. RBAC-lite, attachment context, FAQ import progress, and per-user pin/favorites preparation remain P1/P2; Agent, Wiki, DataSource, IM, and CLI/MCP server remain deferred.

## v0.61 Update

As of 2026-05-31, TASK-001 through TASK-009 are consolidated as knowmate `v0.61`. v0.61 does not start the larger Agent/Wiki/RBAC scope. It strengthens the v0.6 conversation-ready Quick Q&A path with the nearest WeKnora-like knowledge-management and chat UX gaps:

- Tags/categories: KB-scoped tags, document/FAQ tag filtering and batch assignment, with `tag_id` persisted in PostgreSQL and Qdrant payloads.
- Document preview: document preview API, summary/content preview, chunk outline, and frontend preview drawer.
- FAQ import/export/search test: CSV/XLSX append/replace import, row-level import failure summary, CSV/XLSX export, and FAQ search-test drawer.
- Batch UX: requested/succeeded/failed/failures summaries for batch delete/reprocess, task `batch_summary`, and retry entry for failed tasks.
- Settings center: `/#/settings` WeKnora-like shell for models, VectorStore, retrieval, parser status, and storage status; advanced parser/storage providers remain disabled placeholders.
- Chat UX: session search, batch session deletion, and recommended questions generated from FAQ entries and chunk `generated_questions`.

Therefore, items originally recommended for v0.7 around tags, document preview, FAQ import/export/search test, batch feedback, settings center consolidation, session search/batch delete, and suggested questions are now delivered in v0.61. Remaining major gaps are RBAC-lite/workspace, Agent Mode, Wiki Mode, advanced parsing/OCR/MinerU, real object-storage providers, external data-source sync, and deeper observability.

The largest visible gaps against current WeKnora are no longer basic RAG ingestion. They are:

1. Chat productization: multi-turn sessions, streaming output, session list, pin/search/batch management, suggested questions, attachments, and conversation settings.
2. Knowledge base UX depth: tag/category organization, folder import, document preview, document summaries, richer import results, cross-KB navigation, and wiki/graph entry points.
3. Agent/Wiki product modes: visible Agent list/editor, ReAct tool-call display, MCP/web-search settings, Wiki browser, and knowledge graph visualization.
4. Workspace/security UX: login, tenant switching, member management, RBAC-aware buttons, resource ownership, audit logs, and organization/shared-space views.
5. Settings center breadth: one modal/sectioned settings experience covering models, Agent, parser, storage, web search, Ollama, WeKnora Cloud, system info, API info, language/theme/font preferences.
6. Integrations: advanced parsers/OCR/MinerU, image/VLM, ASR, external data sources, object storage providers, vector stores beyond Qdrant, IM channels, Chrome Extension, Mini Program, CLI/MCP.

Recommendation: v0.6 should not chase all WeKnora v0.6 enterprise scope at once. It should focus on the visible Quick Q&A experience: multi-turn sessions, streaming answer, conversation settings, and a better chat sidebar. v0.7 should add knowledge base organization and workspace-lite/RBAC-lite.

## Local knowmate v0.61 Baseline

Visible pages/routes:

- `/#/chat`: conversation-ready Quick Q&A, streaming answer, sources/trace, session search/batch delete, recommended questions, and knowledge-search debug.
- `/#/knowledge-bases`: KB list/create/delete, type selection, model binding, VectorStore selection, indexing strategy.
- `/#/knowledge-bases/:kbId/documents`: document management, tag filtering, upload/import, batch operations, progress feedback, preview drawer, and chunk inspection.
- `/#/knowledge-bases/:kbId/faqs`: FAQ management, tag filtering, CSV/XLSX import/export, and FAQ search test.
- `/#/settings`: settings center for model CRUD/test, Qdrant VectorStore, retrieval/chunking, parser status, and storage status.

Implemented visible functions:

- Document and FAQ knowledge bases.
- Per-KB model binding for QA and Embedding.
- Per-KB indexing strategy toggles for vector, keyword, parent-child, rerank, plus disabled Wiki/KG boundary.
- Async task records for upload/reprocess/rebuild.
- Manual text/Markdown import and lightweight URL import.
- KB-scoped tags, document/FAQ tag filtering, and batch tag assignment.
- Document status, chunk count, failure reason, batch delete/reprocess, and partial failure summaries.
- Document preview drawer with summary, content preview, chunk outline, and chunk content navigation.
- FAQ CSV/XLSX append/replace import, export, and search test.
- Hybrid retrieval with source cards and score metadata.
- Centralized model settings with masked credentials.
- Qdrant VectorStore management.
- Streaming chat sessions with query rewrite, per-message sources/trace, session search, batch delete, pin/unpin, and recommended questions.

Known not implemented from local README:

- Login, RBAC, multi-tenant isolation.
- OCR / MinerU / image parsing.
- True BM25 engine or external sparse engines.
- GraphRAG, multi-dimensional index, query rewrite, multi-turn sessions, streaming answer.
- WeKnoraCloud, Ollama pull, VLM, ASR.
- Agent Mode, Wiki Mode, MCP tools, IM channels, Mini Program, complex external source sync.
- Real object-storage providers and advanced OCR/MinerU provider integration.

## Visible Feature Gap Matrix

### 1. Navigation and Workspace Shell

WeKnora visible surface:

- Sidebar with primary entries: Knowledge Bases, Agents, Organizations, Create Chat, Settings.
- Collapsible session timeline under chat.
- Global command palette via Ctrl/Command+K.
- Tenant selector for users with multi-tenant access.
- Route guards for login, initialization, and tenant/user state.

knowmate v0.61:

- Sidebar has Chat, Knowledge Bases, and Settings Center.
- Chat has a session list with search, pin/unpin, and batch deletion.
- No global command palette, tenant selector, organizations, or agent entry.
- No auth/initialization route guard.

Gap:

- Done: chat session navigation and settings grouping.
- Medium: command palette.
- Later: organizations and tenant selector after auth/RBAC exists.

### 2. Chat / Quick Q&A Experience

WeKnora visible surface:

- Multi-turn chat sessions.
- SSE streaming response.
- Session list grouped by time, with pin/unpin, search, and batch deletion.
- Agent/QA mode distinction.
- Mention/select knowledge bases or files in input.
- Suggested questions for new sessions.
- Message attachments including images.
- Markdown, code highlighting, Mermaid rendering, sanitized HTML.
- Historical reconstruction of agent steps.

knowmate v0.61:

- Conversation-ready Quick Q&A workbench.
- Session sidebar supports create/select/search/rename/delete/batch delete and pin/unpin.
- Streaming quick-answer endpoint and frontend streaming rendering.
- Knowledge-search remains available as a debug panel.
- Markdown answer rendering and source cards.
- Per-message assistant sources and retrieval trace are persisted and displayed.
- Optional follow-up query rewrite shows original and rewritten query in trace.
- Empty new-session state shows recommended questions from FAQ entries and chunk `generated_questions`.
- No attachments, mention selector, Mermaid rendering, or agent-step reconstruction.

Gap:

- Delivered in v0.6/v0.61:
  - `chat_sessions` and `chat_messages`.
  - Session sidebar/list.
  - Streaming quick-answer endpoint.
  - Save sources/retrieval trace with assistant messages.
  - Basic query rewrite for follow-up questions.
  - Suggested questions.
  - Chat search/pin/batch delete.
- Important after v0.61:
  - Knowledge/file mention selector.
  - Mermaid rendering parity.
- Later:
  - Agent step reconstruction and tool-call visualization, once Agent Mode exists.

### 3. Knowledge Base List and Creation

WeKnora visible surface:

- KB list with document/FAQ/wiki modes.
- Knowledge base editor modal with basic info, indexing strategy, model config, chunking, and knowledge graph settings.
- LLM, embedding, rerank, and VLM model binding.
- Vector vs wiki indexing choice.
- Shared/mine/all organization spaces in newer UI.
- KB pinning/user-scoped organization improvements appear in changelog.

knowmate v0.61:

- KB list/create/delete.
- Document/FAQ types only.
- Model binding for QA and Embedding; rerank is available globally/configurationally but not as complete per-KB model workflow.
- Basic indexing strategy toggles and disabled Wiki/KG boundary.
- Chunking config included in create form.
- No VLM binding, no wiki KB, no graph settings, no user pinning, no shared/mine/all spaces.

Gap:

- v0.6: improve KB editor as a real edit modal, not only create-time settings.
- v0.7: tags/categories and pinning.
- Later: Wiki type and GraphRAG settings.

### 4. Document Management

WeKnora visible surface:

- Upload file, upload folder, import URL, manual create.
- Supported formats include PDF, Word, TXT, Markdown, HTML, images, CSV, Excel, PPT, JSON.
- Image upload requires VLM; OCR/MinerU-style advanced parsing is part of broader parsing story.
- Document cards/list with processing status, summary, chunk count, tag/category.
- Document preview for PDF, Docx, Excel, Markdown.
- Full-text reconstruction by merging chunks.
- Batch upload progress and partial-failure summaries.
- Dynamic page size and infinite scroll.

knowmate v0.61:

- Upload file, manual text/Markdown import, lightweight URL import.
- Formats: txt/md/pdf/docx/csv/json/xlsx.
- No folder upload.
- No image, PPT, HTML-as-first-class, OCR, MinerU, VLM parsing.
- Document list has status/filter/chunk count/task status/error.
- Document preview drawer shows summary, content preview, chunk outline, and chunk content navigation.
- Batch delete/reprocess exists with requested/succeeded/failed/failures summaries; upload progress is still simpler than WeKnora.
- Pagination/infinite scroll not WeKnora-level.

Gap:

- Done: document preview, richer processing result display, tags/categories.
- Later: folder upload, better batch upload progress.
- Later: image/OCR/MinerU, PPT, advanced HTML/document reconstruction.

### 5. FAQ Management

WeKnora visible surface:

- FAQ entry cards.
- Create FAQ, import FAQ, search test, export FAQ, batch operations.
- Batch import with progress tracking and persistent result statistics: total, success, failed, skipped, mode, failed entries URL, imported time.
- Tags/categories apply to FAQ entries too.

knowmate v0.61:

- FAQ KB type and FAQ CRUD path exist.
- FAQ entries are indexed into chunks and Qdrant and reused in quick-answer.
- Frontend FAQ management page exists.
- CSV/XLSX import/export, row-level import failure summary, and FAQ search test exist.
- FAQ tag filtering and batch assignment exist.

Gap:

- Done: FAQ import/export, search-test panel, tags, and basic batch operations.
- Later: persistent import task history, failed-entry download URL, and finer-grained batch operations.

### 6. Retrieval and Search Debug

WeKnora visible surface:

- Dense retrieval, BM25/sparse retrieval, GraphRAG, parent-child chunking, multi-dimensional indexing.
- Hybrid retrieval optimizations.
- Per-source parser/storage engine config.
- E2E testing with recall hit rate and BLEU/ROUGE evaluation.
- Full-pipeline visualization appears in public feature overview.

knowmate v0.61:

- Dense Qdrant, app-level jieba + PostgreSQL FTS keyword retrieval, RRF hybrid, optional rerank, parent-child expansion.
- Knowledge-search debug endpoint and UI.
- Per-KB indexing strategy gates vector/keyword/parent-child/rerank.
- No true BM25 engine, GraphRAG, multi-dimensional indexing, E2E evaluation dashboard, or recall metrics.

Gap:

- v0.6: query rewrite + retrieval trace display in chat.
- v0.7: better search evaluation/debug page with saved test cases.
- Later: true BM25/Elasticsearch/OpenSearch/ParadeDB, GraphRAG, evaluation metrics.

### 7. Agent Mode and Tooling

WeKnora visible surface:

- Agent list and custom agent support.
- ReAct progressive multi-step reasoning.
- Tool calling: built-in tools, MCP tools, web search.
- Agent stream display with thinking cards, tool call cards, tool result renderers, approval cards, and plan visualization.
- Agent settings for max iterations, temperature, system prompt with dynamic placeholders.
- Data Analyst agent and agent skills/sandboxed execution appear in version history.

knowmate v0.61:

- No Agent page, no agent model, no tool calling, no MCP, no web search, no agent stream UI.
- Chat is Quick Q&A only.

Gap:

- Not recommended for v0.6 unless chat sessions/streaming are already done.
- Candidate v0.8: Agent Mode MVP with read-only KB retrieval + web search, then MCP approval.

### 8. Wiki Mode and Knowledge Graph

WeKnora visible surface:

- Wiki Mode GA: agent-generated structured interlinked Markdown pages.
- Wiki browser and visual knowledge graph.
- Wiki ingest scales to large KBs with task queue and DLQ.
- Knowledge graph settings for entity extraction and relation mapping.

knowmate v0.61:

- `enable_wiki` and `enable_knowledge_graph` are saved/displayed as unavailable boundaries.
- No wiki page model, wiki browser, graph visualization, graph database, graph extraction, graph retrieval.

Gap:

- Not v0.6.
- Candidate after chat/product basics: v0.8 or v0.9 Wiki MVP.
- First step should be read-only generated wiki pages from KB chunks, before graph visualization.

### 9. Settings Center

WeKnora visible surface:

- Full-screen settings modal or route.
- Sections: General, Models, Agent, Ollama, Parser, Storage, System Info.
- Model settings split by chat/embedding/rerank/VLLM; built-in models show tags and disable edit/delete.
- Model editor supports local Ollama and remote providers.
- Parser engine settings include builtin/simple/MinerU and remote docreader discovery.
- Storage engine settings include local, MinIO, COS, TOS and other object stores.
- System info shows version, edition, commit, build time, Go version, keyword/vector/graph engines, MinIO status, DB migration version.
- General settings include language, theme, font.

knowmate v0.61:

- Model, VectorStore, and retrieval settings are grouped under `/#/settings`.
- Model providers are narrower.
- Parser/storage have visible status sections; advanced providers remain disabled placeholders.
- No Ollama page, Agent settings, system info page, language/theme/font preferences.

Gap:

- Done: consolidated settings shell and parser/storage visible status.
- Medium: system info page or status cards.
- Later: Ollama/WeKnoraCloud/provider marketplace-level UX.

### 10. Model Provider Coverage

WeKnora visible surface:

- Chat/LLM: OpenAI, Azure OpenAI, Anthropic, DeepSeek, Qwen, Zhipu, Hunyuan, Doubao, Gemini, MiniMax, NVIDIA, Novita AI, SiliconFlow, OpenRouter, Ollama.
- Embeddings: Ollama, BGE, GTE, Zhipu, OpenAI-compatible APIs.
- VLM and ASR appear in version history and settings.
- Built-in/hosted model sharing for multi-tenant setups.

knowmate v0.61:

- Qwen/DashScope, DeepSeek, OpenAI-compatible chat/embedding/rerank.
- VLLM/ASR types are enum placeholders.
- No Ollama pull workflow, no VLM, no ASR, no built-in model sharing.

Gap:

- v0.6: support OpenAI-compatible embeddings cleanly and expose provider presets better.
- v0.7: Ollama settings if local deployment is a priority.
- Later: VLM/ASR.

### 11. Vector Store, Storage, and Data Sources

WeKnora visible surface:

- Vector stores: PostgreSQL pgvector, Elasticsearch, Milvus, Weaviate, Qdrant, Apache Doris, Tencent VectorDB.
- Object storage: Local, MinIO, S3, TOS, OSS, KS3, OBS.
- Data-source import: Feishu, Notion, Yuque with sync.
- Chrome Extension capture and ClawHub skill import paths.

knowmate v0.61:

- Qdrant registry/factory and CRUD/test.
- Local file storage only in practice.
- URL import is lightweight one-shot HTML extraction.
- No external source sync or object storage provider UI.

Gap:

- v0.6: keep Qdrant only; improve VectorStore binding validation and display.
- v0.7: storage provider settings if file persistence matters.
- Later: Feishu/Notion/Yuque sync and additional vector stores.

### 12. Auth, RBAC, Organizations, and Audit

WeKnora visible surface:

- Tenant RBAC with Owner/Admin/Contributor/Viewer.
- Per-KB ownership.
- Per-tenant audit log.
- Tenant member management and multi-workspace UX.
- Self-service workspace creation and invite-only workspaces.
- UI hides mutation controls for Viewer/non-creator.
- OIDC and API key auth appear in version history.

knowmate v0.61:

- Single-tenant `DEFAULT_TENANT_ID=10000`.
- No login, users, members, roles, ownership, audit logs, or permission-aware UI.

Gap:

- Not mandatory for v0.6 Quick Q&A, but increasingly blocks WeKnora-like UI parity.
- v0.7 should add RBAC-lite:
  - login/session,
  - user table,
  - workspace/tenant selector shell,
  - Owner/Admin/Viewer minimum roles,
  - hide/disable write buttons for Viewer,
  - audit logs for mutating KB/doc/model operations.

### 13. Observability and System Operations

WeKnora visible surface:

- Langfuse tracing for ReAct loops, token usage, tool calls, and pipeline traces.
- System info page.
- Task queue/DLQ for wiki ingest at scale.
- Automatic database migration on version upgrade.

knowmate v0.61:

- Processing task table and status.
- No Langfuse/trace UI, no token usage display, no system info page, no DLQ, no automatic migration UI.

Gap:

- v0.6: retrieval trace saved with chat message and visible in source panel.
- v0.7: system info page and task history page.
- Later: Langfuse or OpenTelemetry integration.

### 14. External Clients

WeKnora visible surface:

- Web UI, REST API, CLI, Chrome Extension, WeChat Mini Program.
- IM channels: WeCom, Feishu, Slack, Telegram, DingTalk, Mattermost, WeChat.
- CLI command surface: auth, kb, doc, search, chat, etc.

knowmate v0.61:

- Web UI and REST API only.
- No CLI, extension, Mini Program, IM integrations.

Gap:

- Not v0.6.
- CLI could be a useful developer tool after API stabilizes.
- IM/mobile/extension should wait until auth and source management are stable.

## v0.6 Recommended Scope

Theme: Conversation-ready Quick Q&A.

Goal: make the current Quick Q&A path feel like a real WeKnora-style chat product without starting Agent/Wiki/RBAC scope too early.

Recommended deliverables:

1. Chat sessions
   - `chat_sessions` table.
   - `chat_messages` table.
   - session create/list/detail/rename/delete.
   - sidebar session list grouped by recent time.
   - save user query, assistant answer, sources, retrieval mode, model IDs, and timestamps.

2. Streaming answer
   - SSE endpoint for quick-answer.
   - frontend streaming rendering.
   - terminal/final event that includes sources and retrieval metadata.
   - error event with Chinese readable message.

3. Follow-up query rewrite
   - optional query rewrite before retrieval when session history exists.
   - show original query and rewritten query in debug metadata.
   - keep rewrite disabled if model config is missing.

4. Conversation settings
   - per-session or global controls for mode, top_k, rerank, temperature, and system prompt.
   - avoid exposing raw internal config objects.

5. Source and trace UX
   - source panel tied to each assistant message.
   - show vector/keyword/RRF/rerank score, matched child, parent context, rewritten query, retrieval mode.

6. Basic session operations
   - rename session.
   - delete session.
   - pin/unpin if time allows.
   - no batch management unless the session list is already stable.

7. Settings/system polish
   - add System Info page or card: app version, DB status, Qdrant status, Redis status, migration head, model config status.
   - this gives visible operational confidence without becoming full observability.

Suggested v0.6 exclusions:

- Full RBAC.
- Agent Mode.
- Wiki Mode.
- MCP tools.
- IM channels.
- Multi-vector-store fan-out beyond current Qdrant binding.
- Feishu/Notion/Yuque sync.

## v0.7 Recommended Scope

Theme: Knowledge organization and workspace-lite.

Goal: deepen the visible knowledge management UX and lay the minimum collaboration/security foundation.

Recommended deliverables:

1. Tags/categories
   - tag sidebar in document and FAQ pages.
   - create/rename/delete tags.
   - assign tag to one or many documents/FAQ entries.
   - filter by tag.

2. Document preview
   - preview drawer/page for Markdown, TXT, CSV/Excel basic table, PDF text preview, DOCX text preview.
   - chunk-to-source navigation where possible.
   - display document summary when available.

3. FAQ import/export/search test
   - CSV/XLSX import.
   - append/replace modes.
   - import result summary.
   - export FAQ entries.
   - FAQ search-test panel.

4. Batch UX improvements
   - upload progress.
   - partial success/failure summary.
   - retry failed document task from document list.

5. RBAC-lite and workspace shell
   - login.
   - users and tenant/workspace table.
   - Owner/Admin/Viewer roles first.
   - resource ownership on KB.
   - hide mutation UI for Viewer.
   - audit log for create/update/delete/upload/reprocess/model changes.

6. Settings center
   - merge model/retrieval/vector/system into a WeKnora-like settings shell.
   - add parser/storage subsections, even if some providers are disabled placeholders.

Suggested v0.7 exclusions:

- Full four-role RBAC matrix with organization sharing.
- OIDC.
- Advanced object storage providers.
- GraphRAG and Wiki generation.

## Longer-Term Backlog

### v0.8 candidate: Agent Mode MVP

- Agent list.
- Agent editor with model, prompt, max iterations, temperature.
- Agent chat route.
- Tool-call stream display.
- Built-in tools: knowledge search and optional web search.
- No arbitrary code execution in first pass.

### v0.8/v0.9 candidate: Wiki Mode MVP

- Wiki KB type.
- Generate Markdown wiki pages from documents.
- Wiki browser.
- Basic links between pages.
- Later: graph extraction and graph visualization.

### v0.9+ candidate: Advanced parsing and multimodal

- MinerU / OCR parser engine.
- Image document import with VLM captioning.
- PPT support.
- ASR/audio import.
- Advanced object storage providers.

### v1.0 candidate: Enterprise parity

- Full RBAC matrix.
- Organization/shared spaces.
- Audit log UI.
- External data-source sync.
- CLI and API auth.
- Langfuse/trace observability.

## Priority Table

| Priority | Feature | User-visible impact | WeKnora alignment | Suggested version |
| --- | --- | --- | --- | --- |
| P0 | Multi-turn chat sessions | High | High | v0.6 |
| P0 | Streaming answer | High | High | v0.6 |
| P0 | Per-message sources + retrieval trace | High | High | v0.6 |
| P0 | Query rewrite for follow-up questions | High | Medium/High | v0.6 |
| P1 | Session sidebar operations | High | High | v0.6 |
| P1 | Conversation settings | Medium/High | High | v0.6 |
| P1 | System info/status page | Medium | Medium | v0.6 |
| P1 | Tags/categories | High | High | v0.7 |
| P1 | Document preview | High | High | v0.7 |
| P1 | FAQ import/export/search test | Medium/High | High | v0.7 |
| P1 | Upload progress and partial failure summary | Medium/High | High | v0.7 |
| P2 | RBAC-lite | Medium/High | High | v0.7 |
| P2 | Settings center consolidation | Medium | High | v0.7 |
| P2 | Folder upload | Medium | High | v0.7 |
| P3 | Agent Mode MVP | High but broad | High | v0.8 |
| P3 | Wiki Mode MVP | High but broad | High | v0.8/v0.9 |
| P3 | OCR/MinerU/image/VLM | Medium/High | High | v0.9 |
| P3 | External source sync | Medium/High | High | v0.9+ |
| P3 | CLI/Chrome Extension/Mini Program/IM | Medium | High | v1.0+ |

## Suggested Product Narrative

v0.6 should be described as:

> 会话化 Quick Q&A：把当前单轮 RAG 调试台升级为可持续使用的知识库聊天体验，支持多轮追问、流式回答、会话历史、来源追踪和检索解释。

v0.7 should be described as:

> 知识管理增强与工作区基础：补齐标签、预览、FAQ 批量导入导出、批处理反馈和最小权限模型，为后续 Agent / Wiki / 多人协作打地基。

This sequence keeps knowmate aligned with WeKnora while protecting the current v1 Quick Q&A path from over-expansion.
