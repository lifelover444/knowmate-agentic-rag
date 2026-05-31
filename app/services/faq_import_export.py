import csv
import io
import json
from dataclasses import dataclass

from openpyxl import Workbook, load_workbook
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.repositories.faq import FAQEntryRepository
from app.db.repositories.tag import KnowledgeTagRepository
from app.schemas.faq import FAQEntryCreate
from app.services.faq import FAQEntryService

FAQ_COLUMNS = ["question", "answer", "metadata", "enabled", "tag_id"]


@dataclass
class FAQImportError:
    row: int
    error: str


class FAQImportExportService:
    def __init__(self, db: Session, settings: Settings, vector_store, embedder=None) -> None:
        self.db = db
        self.settings = settings
        self.vector_store = vector_store
        self.embedder = embedder
        self.faqs = FAQEntryRepository(db)

    def import_file(self, *, kb_id: str, filename: str, data: bytes, mode: str) -> dict:
        if mode not in {"append", "replace"}:
            raise ValueError("导入模式必须是 append 或 replace")
        rows = _read_rows(filename, data)
        service = FAQEntryService(self.db, self.settings, self.vector_store, embedder=self.embedder)
        if mode == "replace":
            for entry in self.faqs.list_by_knowledge_base(kb_id):
                service.delete(entry)

        imported = 0
        errors: list[FAQImportError] = []
        for row_number, row in rows:
            try:
                payload = self._payload(kb_id, row)
                service.create(kb_id, payload)
                imported += 1
            except Exception as exc:
                errors.append(FAQImportError(row=row_number, error=str(exc)))
        return {
            "imported": imported,
            "failed": len(errors),
            "errors": [error.__dict__ for error in errors],
        }

    def export_rows(self, kb_id: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for entry in self.faqs.list_by_knowledge_base(kb_id):
            rows.append(
                {
                    "question": entry.question,
                    "answer": entry.answer,
                    "metadata": json.dumps(entry.faq_metadata or {}, ensure_ascii=False),
                    "enabled": "true" if entry.enabled else "false",
                    "tag_id": entry.tag_id or "",
                }
            )
        return rows

    def export_csv(self, kb_id: str) -> bytes:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=FAQ_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(self.export_rows(kb_id))
        return buffer.getvalue().encode("utf-8-sig")

    def export_xlsx(self, kb_id: str) -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "FAQs"
        sheet.append(FAQ_COLUMNS)
        for row in self.export_rows(kb_id):
            sheet.append([row[column] for column in FAQ_COLUMNS])
        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    def _payload(self, kb_id: str, row: dict[str, str]) -> FAQEntryCreate:
        question = (row.get("question") or "").strip()
        answer = (row.get("answer") or "").strip()
        if not question:
            raise ValueError("问题不能为空")
        if not answer:
            raise ValueError("答案不能为空")
        metadata_text = (row.get("metadata") or "{}").strip() or "{}"
        try:
            metadata = json.loads(metadata_text)
        except json.JSONDecodeError as exc:
            raise ValueError("metadata 必须是合法 JSON") from exc
        if not isinstance(metadata, dict):
            raise ValueError("metadata 必须是 JSON object")
        tag_id = (row.get("tag_id") or "").strip() or None
        if tag_id is not None:
            tag = KnowledgeTagRepository(self.db).get(tag_id, self.settings.default_tenant_id)
            if tag is None or tag.knowledge_base_id != kb_id:
                raise ValueError("标签不存在")
        return FAQEntryCreate(
            question=question,
            answer=answer,
            metadata=metadata,
            enabled=_parse_bool(row.get("enabled")),
            tag_id=tag_id,
        )


def _read_rows(filename: str, data: bytes) -> list[tuple[int, dict[str, str]]]:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "csv":
        text = data.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        return [(index, {key: value or "" for key, value in row.items()}) for index, row in enumerate(reader, start=2)]
    if suffix == "xlsx":
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(value or "").strip() for value in rows[0]]
        result: list[tuple[int, dict[str, str]]] = []
        for index, values in enumerate(rows[1:], start=2):
            result.append((index, {header: str(value or "") for header, value in zip(headers, values, strict=False)}))
        return result
    raise ValueError("仅支持 CSV 或 XLSX 文件")


def _parse_bool(value: str | None) -> bool:
    normalized = (value or "true").strip().lower()
    return normalized not in {"false", "0", "no", "停用", "禁用"}
