from sqlalchemy.orm import Session

from app.db.models import Knowledge
from app.db.repositories.chunk import ChunkRepository
from app.db.repositories.document import DocumentRepository
from app.schemas.document import DocumentPreviewChunk, DocumentPreviewRead

MAX_PREVIEW_CHARS = 20_000
MAX_CHUNK_PREVIEW_CHARS = 500


class DocumentPreviewService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.documents = DocumentRepository(db)
        self.chunks = ChunkRepository(db)

    def build_preview(self, document_id: str) -> DocumentPreviewRead:
        document = self.documents.get(document_id)
        if document is None:
            raise LookupError("document not found")

        chunks = self.chunks.list_by_document(document.id) if document.parse_status == "completed" else []
        content = _preview_content(document, chunks)
        summary = _summary(document, content)
        return DocumentPreviewRead(
            id=document.id,
            tenant_id=document.tenant_id,
            knowledge_base_id=document.knowledge_base_id,
            title=document.title,
            file_name=document.file_name,
            file_type=document.file_type,
            status=document.parse_status,
            summary=summary,
            content_preview=content[:MAX_PREVIEW_CHARS],
            chunks=[
                DocumentPreviewChunk(
                    id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    chunk_type=chunk.chunk_type,
                    start_at=chunk.start_at,
                    end_at=chunk.end_at,
                    context_header=chunk.context_header,
                    content_preview=chunk.content[:MAX_CHUNK_PREVIEW_CHARS],
                )
                for chunk in chunks
            ],
            error_message=document.error_message,
            metadata=document.doc_metadata or {},
        )


def _preview_content(document: Knowledge, chunks) -> str:
    if document.parse_status == "failed":
        return ""
    if chunks:
        return "\n\n".join(_chunk_text(chunk) for chunk in chunks).strip()
    pages = (document.doc_metadata or {}).get("pages")
    if isinstance(pages, list):
        page_texts = [str(page.get("text") or "").strip() for page in pages if isinstance(page, dict)]
        return "\n\n".join(text for text in page_texts if text).strip()
    return ""


def _chunk_text(chunk) -> str:
    if chunk.context_header:
        return f"{chunk.context_header}\n{chunk.content}".strip()
    return chunk.content.strip()


def _summary(document: Knowledge, content: str) -> str | None:
    metadata = document.doc_metadata or {}
    if metadata.get("summary"):
        return str(metadata["summary"])
    compact = " ".join(content.split())
    return compact[:240] if compact else None
