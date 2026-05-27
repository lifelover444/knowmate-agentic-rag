# AGENTS.md

This file gives Codex and other coding agents project-specific instructions for `knowmate-agentic-rag`.

## Prime Directive

This project must be implemented as a close FastAPI-based reproduction of [Tencent/WeKnora](https://github.com/Tencent/WeKnora).

The intended difference from Tencent/WeKnora is technical stack only:

- Tencent/WeKnora backend: Go.
- knowmate backend: Python / FastAPI.

Unless a user explicitly asks otherwise, product behavior, module boundaries, RAG flow, model-management ideas, parser/chunker design, database concepts, and frontend workflows should follow WeKnora's direction as closely as practical for this repository.

Do not turn this into a different RAG product by inventing unrelated architecture. When adding or changing behavior, first ask: "How does WeKnora structure or solve this?"

## Product Scope

The product name is `knowmate 知友`.

The current v1 priority is WeKnora-style Quick Q&A:

```text
model config
  -> knowledge base creation
  -> document upload
  -> document parsing
  -> adaptive chunking
  -> chunk metadata in PostgreSQL
  -> embeddings in Qdrant
  -> quick-answer retrieval
  -> answer + sources
```

Current scope is single-tenant development with `DEFAULT_TENANT_ID=10000`.

## WeKnora Alignment Rules

When implementing features, prefer WeKnora-compatible concepts and naming where they fit the FastAPI codebase:

- Knowledge base first: all ingestion, chunking, retrieval, and answer behavior should be scoped to a knowledge base.
- Central model configuration: users should configure OpenAI-compatible model settings through the app, and API keys must not be exposed back to the frontend.
- Parser engine registry: document parsing should be selected by file type and knowledge-base rules, not ad hoc conditional logic scattered through services.
- Adaptive chunking: prefer `auto -> heading -> heuristic -> legacy` style strategy selection, with validation and fallback.
- Protected blocks: tables, code blocks, markdown links, image references, and formulas should not be casually split.
- Parent-child chunking: use parent chunks for broader context and child chunks for embedding/retrieval where enabled.
- Sources matter: quick-answer must return sources with enough metadata for users to inspect why an answer was produced.
- Modular integrations: LLM, embedding, vector store, parser, and chunker should stay swappable behind small interfaces or service boundaries.

If WeKnora has an established approach for a feature, follow that approach before designing a new one.

## Architecture Expectations

Use the existing project shape:

```text
app/
  api/v1/          FastAPI routers
  core/            settings, security, logging
  db/              SQLAlchemy models, sessions, repositories
  integrations/    external model and vector-store clients
  rag/             parser, chunker, prompt, answer logic
  schemas/         Pydantic request/response schemas
  services/        application services
  workers/         Celery app and background tasks
frontend/          Vue test workbench
alembic/           database migrations
tests/             pytest tests
```

Keep API handlers thin. Business logic belongs in services, persistence in repositories, and RAG mechanics in `app/rag` or `app/integrations`.

## Backend Rules

- Use FastAPI, Pydantic, SQLAlchemy, Alembic, Celery, Redis, PostgreSQL, and Qdrant.
- Do not introduce Go services.
- Do not add silent local fallback behavior in production quick-answer or document processing. If model configuration is missing, return a clear user-facing error.
- API keys and credentials must be encrypted or kept out of persistent storage. Never log API key plaintext.
- Preserve compatibility of existing response shapes unless a change is explicitly requested.
- Add Alembic migrations for schema changes.
- Keep Qdrant payloads rich enough for source display: document id, chunk id, title, content, context header, parent id, chunk type, and metadata.

## Frontend Rules

- The current frontend is a Vue Chinese test workbench, not a marketing landing page.
- Keep the UI focused on the real workflow: model config, parser/chunking config, knowledge base creation, upload, parsing status, chunk inspection, quick-answer result.
- Do not hide operational state. Users should see whether model configuration, upload, parsing, chunking, and answer retrieval succeeded.
- Error messages should be readable Chinese text. Never render raw objects as `[object Object]`.
- API keys must not be echoed back in the page; show only configured status and last four characters.

## Testing And Verification

For code changes, run the smallest relevant test first, then broaden verification.

Preferred verification commands:

```powershell
python -m pytest -q
ruff check .
python -m compileall app tests
npm --prefix frontend run build
```

For end-to-end ingestion or quick-answer changes, also verify with local services:

```powershell
docker compose up -d postgres redis qdrant
alembic upgrade head
uvicorn app.main:app --reload
celery -A app.workers.celery_app:celery_app worker --loglevel=info --pool=solo
```

Then use the browser or API calls to confirm:

- knowledge base can be created;
- document upload returns a document id;
- worker completes parsing;
- chunks are stored;
- Qdrant has retrievable points;
- quick-answer returns non-empty `answer` and `sources`.

## Implementation Discipline

- Prefer existing patterns in the repository.
- Keep changes scoped to the requested feature.
- Do not revert user changes unless explicitly requested.
- Do not commit `.env`, uploaded files, logs, screenshots, or local runtime artifacts.
- Use fake OpenAI-compatible services or injected test clients for automated tests. Do not require real external API keys in CI-style tests.
- If real API keys are used manually during local validation, never write them to committed files or final responses.

## Roadmap Guardrails

Future work should still follow WeKnora's direction:

- multi-tenant workspace and RBAC;
- model provider management;
- document-source integrations;
- OCR / MinerU-style advanced document parsing;
- rerank and hybrid retrieval;
- agentic retrieval workflows;
- wiki/knowledge-graph style knowledge organization;
- observability for model calls and retrieval traces.

Add these incrementally. Do not compromise the v1 quick-answer path while expanding scope.
