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
    retrieval_view = (ROOT / "frontend" / "src" / "views" / "RetrievalSettingsView.vue").read_text(encoding="utf-8")

    assert "切分配置" in app
    assert "/parser-engines" in app
    assert "/chunker/preview" in app
    assert "parser_engine_rules" in app
    assert "enable_parent_child" in app
    assert "data-testid=\"enable-parent-child\"" not in retrieval_view
    assert "parent-child 固定启用" in retrieval_view
    assert "previewResult" in app


def test_frontend_exposes_mineru_parser_config_form():
    app = frontend_source()
    upload = (ROOT / "frontend" / "src" / "components" / "DocumentUpload.vue").read_text(encoding="utf-8")

    assert "/parser-configs/mineru" in app
    assert "save-mineru-config" in app
    assert "mineru-api-key" in app
    assert "model_version" in app
    assert "MinerU 配置" in app
    assert ".pptx" in upload
    assert ".png" in upload
    assert ".bmp" in upload


def test_frontend_kb_chunking_config_is_fixed_read_only():
    retrieval_view = (ROOT / "frontend" / "src" / "views" / "RetrievalSettingsView.vue").read_text(encoding="utf-8")
    kb_view = (ROOT / "frontend" / "src" / "views" / "KnowledgeBaseView.vue").read_text(encoding="utf-8")
    kb_detail = (ROOT / "frontend" / "src" / "views" / "KnowledgeBaseDetailView.vue").read_text(encoding="utf-8")
    retrieval_store = (ROOT / "frontend" / "src" / "stores" / "retrieval.ts").read_text(encoding="utf-8")

    for source in (retrieval_view, kb_view, kb_detail):
        assert 'v-model="retrieval.chunkStrategy"' not in source
        assert 'v-model="retrieval.chunkSize"' not in source
        assert 'v-model="retrieval.chunkOverlap"' not in source
        assert 'v-model="retrieval.separatorsText"' not in source
        assert 'v-model="retrieval.tokenLimit"' not in source
        assert 'v-model="retrieval.parentChunkSize"' not in source
        assert 'v-model="retrieval.childChunkSize"' not in source
        assert 'v-model="settingsForm.chunkStrategy"' not in source
        assert 'v-model="settingsForm.chunkSize"' not in source
        assert 'v-model="settingsForm.chunkOverlap"' not in source
        assert 'v-model="settingsForm.separatorsText"' not in source
        assert 'v-model="settingsForm.tokenLimit"' not in source

    assert "切分配置：只读展示" in kb_view
    assert "切分配置：只读展示" in kb_detail
    assert 'strategy: "auto"' in retrieval_store
    assert "chunk_size: 512" in retrieval_store
    assert "chunk_overlap: 80" in retrieval_store
    assert 'separators: ["\\n\\n", "\\n", "。"]' in retrieval_store
    assert "token_limit: 0" in retrieval_store
    assert "enable_parent_child: true" in retrieval_store
    assert "parent_chunk_size: 4096" in retrieval_store
    assert "child_chunk_size: 384" in retrieval_store


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
