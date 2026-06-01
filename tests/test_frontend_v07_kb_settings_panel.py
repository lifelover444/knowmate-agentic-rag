from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_detail_settings_can_update_kb_configuration():
    app = frontend_source()

    assert "KBModelConfig" in app
    assert "KBParserSettings" in app
    assert "KBChunkingSettings" in app
    assert "KBIndexingStrategy" in app

    assert "settingsForm" in app
    assert "submitSettings" in app
    assert "validateSettingsModels" in app
    assert "kbStore.updateKnowledgeBase(kbId.value" in app

    assert "基础信息" in app
    assert "QA 模型" in app
    assert "Embedding 模型" in app
    assert "parser rules" in app
    assert "chunking config" in app
    assert "indexing strategy" in app
    assert "vector store" in app

    assert "需要重处理/重建索引" in app
    assert "配置已保存，需要重处理/重建索引后对已有文档生效" in app
    assert "立即重建索引" in app
    assert "QA 模型必须选择 KnowledgeQA 类型" in app
    assert "Embedding 模型必须选择 Embedding 类型" in app
    assert "Wiki 暂未实现" in app
    assert "Graph 暂未实现" in app
