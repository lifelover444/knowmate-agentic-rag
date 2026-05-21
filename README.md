# knowmate知友

FastAPI implementation of the WeKnora-style v1 quick-answer RAG chain.

## Quickstart

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
docker compose up -d postgres redis qdrant
alembic upgrade head
cd frontend
npm install
npm run build
cd ..
celery -A app.workers.celery_app.celery_app worker --loglevel=info
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` for the Vue quick-answer workbench.

## Core APIs

- `POST /api/v1/knowledge-bases`
- `GET /api/v1/knowledge-bases/{kb_id}`
- `POST /api/v1/knowledge-bases/{kb_id}/documents/file`
- `GET /api/v1/documents/{document_id}`
- `GET /api/v1/documents/{document_id}/chunks`
- `POST /api/v1/quick-answer`
