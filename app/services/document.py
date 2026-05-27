import hashlib
from pathlib import Path

from fastapi import UploadFile

from app.core.config import Settings
from app.db.models import Knowledge
from app.db.repositories.document import DocumentRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository


class DocumentService:
    def __init__(
        self,
        document_repo: DocumentRepository,
        kb_repo: KnowledgeBaseRepository,
        settings: Settings,
        upload_dir: Path | None = None,
    ) -> None:
        self.document_repo = document_repo
        self.kb_repo = kb_repo
        self.settings = settings
        self.upload_dir = upload_dir or settings.upload_dir

    def create_from_upload(self, kb_id: str, file: UploadFile) -> Knowledge:
        kb = self.kb_repo.get(kb_id, self.settings.default_tenant_id)
        if kb is None:
            raise LookupError("knowledge base not found")

        data = file.file.read()
        file_hash = hashlib.sha256(data).hexdigest()
        document_id = file_hash[:8] + "-" + hashlib.sha1((kb_id + file_hash).encode()).hexdigest()[:27]
        target_dir = self.upload_dir / kb_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{document_id}_{file.filename}"
        target_path.write_bytes(data)

        document = Knowledge(
            id=document_id,
            tenant_id=self.settings.default_tenant_id,
            knowledge_base_id=kb_id,
            type="file",
            title=file.filename or target_path.name,
            source="upload",
            parse_status="pending",
            enable_status="enabled",
            embedding_model_id=kb.embedding_model_id,
            file_name=file.filename,
            file_type=Path(file.filename or "").suffix.lower().lstrip("."),
            file_size=len(data),
            file_path=str(target_path),
            file_hash=file_hash,
            storage_size=len(data),
            doc_metadata={},
        )
        return self.document_repo.create(document)

    def soft_delete(self, document: Knowledge, vector_store=None) -> Knowledge:
        deleted = self.document_repo.soft_delete(document)
        if vector_store is not None and hasattr(vector_store, "delete_by_knowledge_id"):
            vector_store.delete_by_knowledge_id(document.id)
        return deleted
