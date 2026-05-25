from types import SimpleNamespace

from app.core.config import Settings
from app.integrations.llm_openai import OpenAIEmbedder


class FakeEmbeddingsAPI:
    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    def create(self, *, model: str, input: list[str], dimensions: int):
        self.batch_sizes.append(len(input))
        data = [
            SimpleNamespace(embedding=[float(len(text)), float(index), float(dimensions)])
            for index, text in enumerate(input)
        ]
        return SimpleNamespace(data=data)


def test_openai_embedder_batches_inputs_for_qwen_limit():
    embedder = OpenAIEmbedder(Settings(openai_api_key="sk-test", embedding_dimension=3, embedding_batch_size=10))
    fake_embeddings = FakeEmbeddingsAPI()
    embedder.client = SimpleNamespace(embeddings=fake_embeddings)

    vectors = embedder.embed_many([f"chunk-{index}" for index in range(23)])

    assert fake_embeddings.batch_sizes == [10, 10, 3]
    assert len(vectors) == 23
