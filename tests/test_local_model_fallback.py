from app.core.config import Settings
from app.integrations.llm_openai import OpenAIChatModel, OpenAIEmbedder


def test_default_openai_key_uses_local_deterministic_fallback():
    settings = Settings(openai_api_key="change-me", embedding_dimension=4)

    embedder = OpenAIEmbedder(settings)
    chat_model = OpenAIChatModel(settings)

    assert embedder.embed("knowmate") == embedder.embed("knowmate")
    assert len(embedder.embed("knowmate")) == 4
    assert (
        chat_model.complete(
            [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "Context:\nKnowmate local answer\n\nQuestion:\nWhat?"},
            ]
        )
        == "Knowmate local answer"
    )
