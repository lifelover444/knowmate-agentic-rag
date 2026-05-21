from app.rag.quick_answer import QuickAnswerEngine


def test_quick_answer_uses_retrieved_sources(fake_embedder, fake_chat_model, fake_vector_store):
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-1",
            "knowledge_id": "doc-1",
            "knowledge_base_id": "kb-1",
            "content": "Knowmate answers from private documents.",
            "score": 0.91,
        }
    ]
    engine = QuickAnswerEngine(
        embedder=fake_embedder,
        chat_model=fake_chat_model,
        vector_store=fake_vector_store,
    )

    result = engine.answer(knowledge_base_id="kb-1", query="What does Knowmate do?", top_k=5)

    assert result.answer == "Knowmate answers from private documents."
    assert result.sources[0].chunk_id == "chunk-1"
    assert result.sources[0].score == 0.91


def test_quick_answer_returns_fallback_without_sources(fake_embedder, fake_chat_model, fake_vector_store):
    fake_vector_store.results = []
    engine = QuickAnswerEngine(
        embedder=fake_embedder,
        chat_model=fake_chat_model,
        vector_store=fake_vector_store,
    )

    result = engine.answer(knowledge_base_id="kb-1", query="Unknown?", top_k=5)

    assert result.answer == "没有在知识库中找到可引用的内容。"
    assert result.sources == []
