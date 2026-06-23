from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader, PdfWriter


class PdfSplitError(RuntimeError):
    pass


@dataclass(frozen=True)
class PdfPart:
    index: int
    page_start: int
    page_end: int
    path: Path


def get_pdf_page_count(path: Path) -> int:
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise PdfSplitError("PDF 已加密，无法自动分片解析")
        return len(reader.pages)
    except PdfSplitError:
        raise
    except Exception as exc:
        raise PdfSplitError(f"PDF 页数读取失败：{exc}") from exc


def split_pdf_by_page_limit(path: Path, output_dir: Path, *, max_pages: int = 200) -> list[PdfPart]:
    if max_pages < 1:
        raise ValueError("max_pages must be greater than 0")
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise PdfSplitError("PDF 已加密，无法自动分片解析")
        total_pages = len(reader.pages)
        if total_pages == 0:
            raise PdfSplitError("PDF 没有可解析页面")
        output_dir.mkdir(parents=True, exist_ok=True)
        parts: list[PdfPart] = []
        for start in range(0, total_pages, max_pages):
            end = min(start + max_pages, total_pages)
            writer = PdfWriter()
            for page_index in range(start, end):
                writer.add_page(reader.pages[page_index])
            part_index = len(parts) + 1
            part_path = output_dir / f"{path.stem}_part{part_index:03d}_pages{start + 1:03d}-{end:03d}.pdf"
            with part_path.open("wb") as file:
                writer.write(file)
            parts.append(PdfPart(index=part_index, page_start=start + 1, page_end=end, path=part_path))
        return parts
    except PdfSplitError:
        raise
    except Exception as exc:
        raise PdfSplitError(f"PDF 分片写入失败：{exc}") from exc
