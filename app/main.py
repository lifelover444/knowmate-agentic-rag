from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.api.v1.documents import create_document_from_file
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import make_session_factory
from app.integrations.llm_openai import OpenAIChatModel, OpenAIEmbedder
from app.integrations.qdrant_store import QdrantVectorStore


def create_app(
    *,
    settings: Settings | None = None,
    session_factory: Callable[[], Session] | None = None,
    embedder=None,
    chat_model=None,
    vector_store=None,
) -> FastAPI:
    configure_logging()
    resolved_settings = settings or get_settings()
    resolved_settings.upload_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title=resolved_settings.app_name)
    app.state.settings = resolved_settings
    app.state.session_factory = session_factory or make_session_factory(resolved_settings)
    app.state.embedder = embedder or OpenAIEmbedder(resolved_settings)
    app.state.chat_model = chat_model or OpenAIChatModel(resolved_settings)
    app.state.vector_store = vector_store or QdrantVectorStore(resolved_settings)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return Response(status_code=204)

    app.include_router(api_router, prefix=resolved_settings.api_v1_prefix)
    app.add_api_route(
        f"{resolved_settings.api_v1_prefix}/knowledge-bases/{{kb_id}}/documents/file",
        create_document_from_file,
        methods=["POST"],
        status_code=201,
        tags=["documents"],
    )

    frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if (frontend_dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend-assets")

    @app.get("/", include_in_schema=False)
    def frontend_index():
        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return HTMLResponse(
            "<h1>knowmate知友</h1><p>前端页面尚未构建，请运行 <code>npm --prefix frontend run build</code>。</p>",
            status_code=200,
        )

    return app


app = create_app()
