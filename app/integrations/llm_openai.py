import hashlib

from openai import OpenAI

from app.core.config import Settings


def _use_local_fallback(api_key: str) -> bool:
    return api_key.strip().lower() in {"", "change-me", "mock", "test"}


class OpenAIEmbedder:
    def __init__(self, settings: Settings) -> None:
        self.local_fallback = _use_local_fallback(settings.openai_api_key)
        self.client = (
            None
            if self.local_fallback
            else OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        )
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimension

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if self.local_fallback:
            return [self._local_embedding(text) for text in texts]
        sanitized = [text[:20000] for text in texts]
        if self.client is None:
            raise RuntimeError("OpenAI client is not configured")
        response = self.client.embeddings.create(
            model=self.model,
            input=sanitized,
            dimensions=self.dimensions,
        )
        return [item.embedding for item in response.data]

    def _local_embedding(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        for idx in range(self.dimensions):
            byte = digest[idx % len(digest)]
            values.append((byte / 127.5) - 1.0)
        return values


class OpenAIChatModel:
    def __init__(self, settings: Settings) -> None:
        self.local_fallback = _use_local_fallback(settings.openai_api_key)
        self.client = (
            None
            if self.local_fallback
            else OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        )
        self.model = settings.chat_model

    def complete(self, messages: list[dict[str, str]]) -> str:
        if self.local_fallback:
            return self._local_complete(messages)
        if self.client is None:
            raise RuntimeError("OpenAI client is not configured")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
        )
        return response.choices[0].message.content or ""

    def _local_complete(self, messages: list[dict[str, str]]) -> str:
        user_content = messages[-1]["content"] if messages else ""
        marker = "Context:\n"
        if marker not in user_content:
            return "没有在知识库中找到可引用的内容。"
        context = user_content.split(marker, 1)[1].split("\n\nQuestion:", 1)[0].strip()
        return context.split("\n\n---\n\n", 1)[0].strip() if context else "没有在知识库中找到可引用的内容。"
