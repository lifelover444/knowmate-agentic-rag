from dataclasses import dataclass
from pathlib import Path

SUPPORTED_ATTACHMENT_TYPES = {"txt", "md", "markdown", "csv", "json"}
MAX_ATTACHMENT_COUNT = 5
MAX_ATTACHMENT_BYTES = 64 * 1024
MAX_ATTACHMENT_LINES = 200
MAX_ATTACHMENT_CHARS = 12000


@dataclass(frozen=True)
class PreparedAttachment:
    filename: str
    file_type: str
    mime_type: str | None
    size_bytes: int
    line_count: int
    char_count: int
    truncated: bool
    content: str

    def metadata(self) -> dict:
        return {
            "filename": self.filename,
            "file_type": self.file_type,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "line_count": self.line_count,
            "char_count": self.char_count,
            "truncated": self.truncated,
        }


def prepare_attachments(attachments: list) -> tuple[list[PreparedAttachment], str]:
    if not attachments:
        return [], ""
    if len(attachments) > MAX_ATTACHMENT_COUNT:
        raise ValueError(f"本轮最多支持 {MAX_ATTACHMENT_COUNT} 个临时附件")
    prepared = [_prepare_attachment(item) for item in attachments]
    return prepared, build_attachments_context(prepared)


def build_attachments_context(attachments: list[PreparedAttachment]) -> str:
    if not attachments:
        return ""
    blocks = ["<attachments>"]
    for index, attachment in enumerate(attachments, start=1):
        truncated_label = "，内容已截断" if attachment.truncated else ""
        blocks.append(
            "\n".join(
                [
                    f"[{index}] {attachment.filename} ({attachment.file_type}{truncated_label})",
                    attachment.content,
                ]
            )
        )
    blocks.append("</attachments>")
    return "\n\n".join(blocks)


def _prepare_attachment(attachment) -> PreparedAttachment:
    data = attachment.model_dump() if hasattr(attachment, "model_dump") else dict(attachment)
    filename = str(data.get("filename") or data.get("name") or "").strip()
    if not filename:
        raise ValueError("附件缺少文件名")
    file_type = Path(filename).suffix.lower().lstrip(".")
    if file_type not in SUPPORTED_ATTACHMENT_TYPES:
        raise ValueError(f"不支持的附件类型：{filename}，当前仅支持 txt/md/csv/json")
    content = str(data.get("content") or "")
    size_bytes = int(data.get("size") or len(content.encode("utf-8")))
    if size_bytes > MAX_ATTACHMENT_BYTES:
        raise ValueError(f"附件 {filename} 超过大小限制，当前仅支持 64KB 以内的文本附件")
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines()
    truncated = False
    if len(lines) > MAX_ATTACHMENT_LINES:
        normalized = "\n".join(lines[:MAX_ATTACHMENT_LINES])
        truncated = True
    if len(normalized) > MAX_ATTACHMENT_CHARS:
        normalized = normalized[:MAX_ATTACHMENT_CHARS].rstrip()
        truncated = True
    if truncated:
        normalized = f"{normalized}\n...[附件内容已截断]"
    return PreparedAttachment(
        filename=filename,
        file_type=file_type,
        mime_type=data.get("mime_type"),
        size_bytes=size_bytes,
        line_count=len(lines),
        char_count=len(content),
        truncated=truncated,
        content=normalized,
    )
