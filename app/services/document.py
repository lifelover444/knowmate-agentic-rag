import hashlib
import re
import uuid
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import UploadFile

from app.core.config import Settings
from app.db.models import Knowledge
from app.db.repositories.chunk import ChunkRepository
from app.db.repositories.document import DocumentRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.db.repositories.task import ProcessingTaskRepository
from app.services.processing_spans import ProcessingSpanService


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

    def create_from_upload(self, kb_id: str, file: UploadFile, *, tag_id: str | None = None) -> Knowledge:
        kb = self.kb_repo.get(kb_id, self.settings.default_tenant_id)
        if kb is None:
            raise LookupError("knowledge base not found")

        data = file.file.read()
        file_hash = hashlib.sha256(data).hexdigest()
        if self.document_repo.find_active_by_file_hash(kb_id, file_hash) is not None:
            raise ValueError("该文件已上传，请勿重复上传。")
        base_document_id = file_hash[:8] + "-" + hashlib.sha1((kb_id + file_hash).encode()).hexdigest()[:27]
        document_id = base_document_id
        while self.document_repo.get_including_deleted(document_id) is not None:
            document_id = str(uuid.uuid4())
        target_dir = self.upload_dir / kb_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{document_id}_{file.filename}"
        target_path.write_bytes(data)

        document = Knowledge(
            id=document_id,
            tenant_id=self.settings.default_tenant_id,
            knowledge_base_id=kb_id,
            type="file",
            source_type="file",
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
            tag_id=tag_id,
            doc_metadata={},
        )
        return self.document_repo.create(document)

    def create_from_text(
        self,
        kb_id: str,
        *,
        title: str,
        content: str,
        source_type: str,
        file_type: str,
        source: str,
        metadata: dict | None = None,
        tag_id: str | None = None,
    ) -> Knowledge:
        kb = self.kb_repo.get(kb_id, self.settings.default_tenant_id)
        if kb is None:
            raise LookupError("knowledge base not found")
        data = content.encode("utf-8")
        document_id = str(uuid.uuid4())
        target_dir = self.upload_dir / kb_id
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_title = re.sub(r"[^0-9A-Za-z._-]+", "_", title).strip("_") or document_id
        target_path = target_dir / f"{document_id}_{safe_title}.{file_type}"
        target_path.write_bytes(data)
        return self.document_repo.create(
            Knowledge(
                id=document_id,
                tenant_id=self.settings.default_tenant_id,
                knowledge_base_id=kb_id,
                type=source_type,
                source_type=source_type,
                title=title,
                source=source,
                parse_status="pending",
                enable_status="enabled",
                embedding_model_id=kb.embedding_model_id,
                file_name=target_path.name,
                file_type=file_type,
                file_size=len(data),
                file_path=str(target_path),
                file_hash=hashlib.sha256(data).hexdigest(),
                storage_size=len(data),
                tag_id=tag_id,
                doc_metadata=metadata or {},
            )
        )

    def create_from_url(self, kb_id: str, url: str, *, tag_id: str | None = None) -> Knowledge:
        html = fetch_url_html(url)
        title, text = html_to_readable_text(html)
        if not text.strip():
            raise ValueError("URL 内容为空，无法导入")
        return self.create_from_text(
            kb_id,
            title=title or url,
            content=f"# {title or url}\n\n{text}",
            source_type="url",
            file_type="md",
            source=url,
            metadata={"url": url},
            tag_id=tag_id,
        )

    def soft_delete(self, document: Knowledge, vector_store=None) -> Knowledge:
        deleted = self.document_repo.soft_delete(document)
        ChunkRepository(self.document_repo.db).bm25_delete_by_document(document.id)
        if vector_store is not None and hasattr(vector_store, "delete_by_knowledge_id"):
            vector_store.delete_by_knowledge_id(document.id)
        return deleted

    def cancel_parse(self, document: Knowledge) -> Knowledge:
        if document.parse_status in {"completed", "failed"}:
            raise ValueError("解析已结束，无法取消")
        if document.parse_status != "cancelled":
            document.parse_status = "cancelled"
            document.error_message = "用户已取消解析"
            document = self.document_repo.save(document)
        ProcessingTaskRepository(self.document_repo.db).cancel_active_for_document(document.id)
        spans = ProcessingSpanService(self.document_repo.db)
        timeline = spans.get_timeline(document.id)
        if timeline.attempt > 0:
            spans.cancel_attempt(document.id, timeline.attempt)
        return document

    def move_to_knowledge_base(self, document: Knowledge, target_kb_id: str, vector_store=None) -> Knowledge:
        target_kb = self.kb_repo.get(target_kb_id, document.tenant_id)
        if target_kb is None:
            raise LookupError("目标知识库不存在")
        source_kb = self.kb_repo.get(document.knowledge_base_id, document.tenant_id)
        if source_kb is None:
            raise LookupError("源知识库不存在")
        if source_kb.id == target_kb.id:
            raise ValueError("源知识库和目标知识库不能相同")
        if source_kb.kb_type != target_kb.kb_type:
            raise ValueError("目标知识库类型必须与源知识库一致")
        if source_kb.embedding_model_id != target_kb.embedding_model_id:
            raise ValueError("目标知识库必须使用相同的 Embedding 模型")
        moved = self.document_repo.move_to_knowledge_base(document, target_kb.id, target_kb.embedding_model_id)
        if vector_store is not None and hasattr(vector_store, "move_knowledge_to_kb"):
            vector_store.move_knowledge_to_kb(knowledge_id=document.id, target_kb_id=target_kb.id)
        return moved


def fetch_url_html(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("仅支持 http/https URL 导入")
    host = parsed.hostname or ""
    if _is_blocked_host(host):
        raise ValueError("不支持导入本地或内网地址")
    request = Request(url, headers={"User-Agent": "knowmate-url-import/0.5"})
    try:
        with urlopen(request, timeout=10) as response:
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type:
                raise ValueError("URL 响应不是 HTML 内容")
            data = response.read(2_000_000)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"URL 导入失败：{exc}") from exc
    return data.decode("utf-8", errors="replace")


def _is_blocked_host(host: str) -> bool:
    lowered = host.lower()
    if lowered in {"localhost", "0.0.0.0"} or lowered.endswith(".localhost"):
        return True
    if lowered.startswith("127.") or lowered.startswith("10.") or lowered.startswith("192.168."):
        return True
    if lowered.startswith("172."):
        parts = lowered.split(".")
        if len(parts) > 1 and parts[1].isdigit() and 16 <= int(parts[1]) <= 31:
            return True
    return False


class _ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "title":
            self._in_title = True
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title = f"{self.title} {text}".strip()
        elif self._skip_depth == 0:
            self.parts.append(text)


def html_to_readable_text(html: str) -> tuple[str, str]:
    parser = _ReadableHTMLParser()
    parser.feed(html)
    return parser.title, "\n".join(parser.parts)
