from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_exposes_parser_and_chunking_settings():
    app = frontend_source()

    assert "切分配置" in app
    assert "/parser-engines" in app
    assert "/chunker/preview" in app
    assert "parser_engine_rules" in app
    assert "enable_parent_child" in app
    assert "previewResult" in app


def test_frontend_chunk_preview_exposes_weknora_debug_fields():
    app = frontend_source()

    assert "策略链" in app
    assert "被拒绝层级" in app
    assert "拒绝原因" in app
    assert "文档画像" in app
    assert "标题数" in app
    assert "分页符" in app
    assert "章节标记" in app
    assert "表格/代码" in app
    assert "检测语言" in app
    assert "保护块统计" in app
    assert "Chunk 分布" in app
    assert "approx tokens" in app
    assert "context_header" in app
    assert "start/end" in app


def test_frontend_chunk_preview_exposes_token_limit_debug_fields():
    app = frontend_source()

    assert "Token 上限" in app
    assert "生效 chunk size" in app
    assert "平均 tokens" in app
    assert "最大 tokens" in app
