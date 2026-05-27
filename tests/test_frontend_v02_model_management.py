from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frontend_exposes_v02_model_binding_retrieval_and_reprocess_controls():
    app = (ROOT / "frontend" / "src" / "App.vue").read_text(encoding="utf-8")

    assert "/models" in app
    assert "selectedChatModelId" in app
    assert "selectedEmbeddingModelId" in app
    assert "embedding_model_id: selectedEmbeddingModelId.value" in app
    assert "summary_model_id: selectedChatModelId.value" in app
    assert "/retrieval-config" in app
    assert "retrievalVectorThreshold" in app
    assert "/reprocess" in app
    assert "parent_chunk_id" in app
    assert "chunk_type" in app


def test_frontend_supports_separate_qa_and_embedding_model_credentials():
    app = (ROOT / "frontend" / "src" / "App.vue").read_text(encoding="utf-8")

    assert "qaProvider" in app
    assert "embeddingProvider" in app
    assert "saveQaModel" in app
    assert "saveEmbeddingModel" in app
    assert "selectedChatModelId" in app
    assert "selectedEmbeddingModelId" in app
    assert "const modelId = type === \"Embedding\" ? selectedEmbeddingModelId.value : selectedChatModelId.value" in app
    assert "model_id: modelId || undefined" in app
    assert "deepseek" in app
    assert "save-model" not in app
