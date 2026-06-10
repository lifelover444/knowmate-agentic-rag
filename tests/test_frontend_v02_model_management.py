from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_exposes_v02_model_binding_retrieval_and_reprocess_controls():
    app = frontend_source()

    assert "/models" in app
    assert "selectedChatModelId" in app
    assert "selectedEmbeddingModelId" in app
    assert "embedding_model_id" in app
    assert "summary_model_id" in app
    assert "/retrieval-config" in app
    assert "retrievalVectorThreshold" in app
    assert "/reprocess" in app
    assert "parent_chunk_id" in app
    assert "chunk_type" in app


def test_frontend_supports_separate_qa_and_embedding_model_credentials():
    app = frontend_source()

    assert "qaProvider" in app
    assert "embeddingProvider" in app
    assert "saveQaModel" in app or "saveModel" in app
    assert "saveEmbeddingModel" in app or "saveModel" in app
    assert "selectedChatModelId" in app
    assert "selectedEmbeddingModelId" in app
    assert "model_id" in app
    assert "deepseek" in app


def test_frontend_uses_provider_presets_and_grouped_model_list():
    app = frontend_source()

    assert "/models/providers" in app
    assert "providerPresets" in app
    assert "loadProviderPresets" in app
    assert "applyProviderPreset" in app
    assert "default_models" in app
    assert "default_urls" in app
    assert "modelGroups" in app
    assert "KnowledgeQA 模型组" in app
    assert "Embedding 模型组" in app
    assert "Rerank 模型组" in app


def test_frontend_uses_qwen_rerank_preset_instead_of_qwen_plus():
    app = frontend_source()

    assert "rerankModel" in app
    assert "qwen3-rerank" in app
    assert "compatible-api/v1/reranks" in app


def test_frontend_keeps_kb_parent_child_and_rerank_fixed_on():
    app = frontend_source()
    kb_view = (ROOT / "frontend" / "src" / "views" / "KnowledgeBaseView.vue").read_text(encoding="utf-8")
    kb_detail = (ROOT / "frontend" / "src" / "views" / "KnowledgeBaseDetailView.vue").read_text(encoding="utf-8")

    assert "updateKnowledgeBase" in app
    assert "edit-kb-config" in app
    assert "submitEdit" in app
    assert "enable_parent_child: true" in kb_view
    assert "enable_rerank: true" in kb_view
    assert "enable_parent_child: true" in kb_detail
    assert "enable_rerank: true" in kb_detail
    assert "v0.9 固定启用" in kb_view
    assert "v0.9 固定启用" in kb_detail
    assert "v-model=\"createForm.enable_parent_child\"" not in kb_view
    assert "v-model=\"createForm.enable_rerank\"" not in kb_view
    assert "v-model=\"editForm.enable_parent_child\"" not in kb_view
    assert "v-model=\"editForm.enable_rerank\"" not in kb_view
    assert "v-model=\"settingsForm.enableParentChild\"" not in kb_detail
    assert "v-model=\"settingsForm.enableRerank\"" not in kb_detail


def test_frontend_kb_model_vectorstore_and_indexing_are_fixed_to_v09_mainline():
    models_store = (ROOT / "frontend" / "src" / "stores" / "models.ts").read_text(encoding="utf-8")
    kb_view = (ROOT / "frontend" / "src" / "views" / "KnowledgeBaseView.vue").read_text(encoding="utf-8")
    kb_detail = (ROOT / "frontend" / "src" / "views" / "KnowledgeBaseDetailView.vue").read_text(encoding="utf-8")

    assert "isRealSelectableModel" in models_store
    assert 'model.model_name !== "fake-embedding"' in models_store
    assert 'model.type === "Embedding"' in models_store
    assert 'model.type === "KnowledgeQA"' in models_store

    for source in (kb_view, kb_detail):
        assert 'v-model="createForm.vector_store_id"' not in source
        assert 'v-model="editForm.vector_store_id"' not in source
        assert 'v-model="settingsForm.vector_store_id"' not in source
        assert 'v-model="createForm.enable_vector"' not in source
        assert 'v-model="createForm.enable_keyword"' not in source
        assert 'v-model="editForm.enable_vector"' not in source
        assert 'v-model="editForm.enable_keyword"' not in source
        assert 'v-model="settingsForm.enableVector"' not in source
        assert 'v-model="settingsForm.enableKeyword"' not in source
        assert "VectorStore：默认 Qdrant" in source
        assert "vector 固定开启" in source
        assert "keyword 固定开启" in source
        assert "Wiki 关闭" in source
        assert "Knowledge Graph 关闭" in source

    assert "vector_store_id: null" in kb_view
    assert "enable_vector: true" in kb_view
    assert "enable_keyword: true" in kb_view
    assert "enable_vector: true" in kb_detail
    assert "enable_keyword: true" in kb_detail
