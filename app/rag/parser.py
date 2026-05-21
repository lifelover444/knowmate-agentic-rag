from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    text: str


class DocumentParser:
    def parse(self, path: Path) -> ParsedDocument:
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md"}:
            return ParsedDocument(title=path.name, text=path.read_text(encoding="utf-8").strip())
        if suffix == ".pdf":
            return ParsedDocument(title=path.name, text=self._parse_pdf(path).strip())
        if suffix == ".docx":
            return ParsedDocument(title=path.name, text=self._parse_docx(path).strip())
        raise ValueError(f"Unsupported document type: {suffix or '<none>'}")

    def _parse_pdf(self, path: Path) -> str:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)

    def _parse_docx(self, path: Path) -> str:
        from docx import Document

        doc = Document(str(path))
        return "\n".join(paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip())
