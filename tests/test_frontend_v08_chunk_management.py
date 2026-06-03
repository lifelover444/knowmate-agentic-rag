from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_frontend_chunk_management_wiring():
    store = read("frontend/src/stores/knowledgeBase.ts")
    view = read("frontend/src/views/DocumentsView.vue")
    types = read("frontend/src/types/api.ts")

    assert "ChunkUpdatePayload" in types
    assert "ChunkUpdateResponse" in types
    assert "GeneratedQuestion" in types
    assert "search_text" in types
    assert "currentChunkDetail" in store
    assert "loadChunkById" in store
    assert "/chunks/by-id/${chunkId}" in store
    assert "updateChunk" in store
    assert "/chunks/${knowledgeId}/${chunkId}" in store
    assert "addGeneratedQuestion" in store
    assert "/chunks/by-id/${chunkId}/questions" in store
    assert "deleteGeneratedQuestion" in store
    assert "chunk-detail-drawer" in view
    assert "openChunkDetail" in view
    assert "保存 chunk" in view
    assert "启用 chunk" in view
    assert "生成问题" in view
    assert "新增生成问题" in view
    assert "删除生成问题" in view
    assert "内容变化后需要重建 embedding" in view
