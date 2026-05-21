from pathlib import Path

import pytest

from app.rag.parser import DocumentParser


def test_parser_reads_plain_text(tmp_path: Path):
    file_path = tmp_path / "note.txt"
    file_path.write_text("knowmate stores chunks for quick answer", encoding="utf-8")

    parsed = DocumentParser().parse(file_path)

    assert parsed.text == "knowmate stores chunks for quick answer"
    assert parsed.title == "note.txt"


def test_parser_rejects_unsupported_extension(tmp_path: Path):
    file_path = tmp_path / "data.bin"
    file_path.write_bytes(b"\x00\x01")

    with pytest.raises(ValueError, match="Unsupported document type"):
        DocumentParser().parse(file_path)
