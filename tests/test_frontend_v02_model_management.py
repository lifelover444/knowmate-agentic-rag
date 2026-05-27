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
