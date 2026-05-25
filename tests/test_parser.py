from pathlib import Path

import pytest

from app.rag.parser import DocumentParser, ParserEngineRegistry


def test_parser_reads_plain_text_as_structured_document(tmp_path: Path):
    file_path = tmp_path / "note.txt"
    file_path.write_text("knowmate stores chunks for quick answer", encoding="utf-8")

    parsed = DocumentParser().parse(file_path)

    assert parsed.content == "knowmate stores chunks for quick answer"
    assert parsed.text == parsed.content
    assert parsed.title == "note.txt"
    assert parsed.metadata["file_type"] == "txt"
    assert parsed.pages == []


def test_markdown_parser_normalizes_tables(tmp_path: Path):
    file_path = tmp_path / "table.md"
    file_path.write_text("|姓名|年龄|\n|:---|---:|\n|张三|18|", encoding="utf-8")

    parsed = DocumentParser().parse(file_path)

    assert "| 姓名 | 年龄 |" in parsed.content
    assert "| :--- | ---: |" in parsed.content


def test_parser_engine_registry_lists_builtin_support_and_rejects_unsupported(tmp_path: Path):
    registry = ParserEngineRegistry()

    engines = registry.list_engines()

    builtin = next(engine for engine in engines if engine["name"] == "builtin")
    assert {"txt", "md", "pdf", "docx", "csv", "json", "xlsx"} <= set(builtin["file_types"])
    assert builtin["available"] is True

    file_path = tmp_path / "data.bin"
    file_path.write_bytes(b"\x00\x01")
    with pytest.raises(ValueError, match="Unsupported file type"):
        DocumentParser(registry=registry).parse(file_path)
