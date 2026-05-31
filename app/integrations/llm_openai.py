import hashlib
from dataclasses import dataclass

from openai import OpenAI

from app.core.config import Settings


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    provider: str
    base_url: str
    api_key: str
    chat_model: str
    embedding_model: str
    embedding_dimension: int


def _use_local_fallback(api_key: str) -> bool:
    return api_key.strip().lower() in {"", "change-me", "mock", "test"}


class OpenAIEmbedder:
    def __init__(self, config: Settings | OpenAICompatibleConfig) -> None:
        self.local_fallback = isinstance(config, Settings) and _use_local_fallback(config.openai_api_key)
        api_key = config.openai_api_key if isinstance(config, Settings) else config.api_key
        base_url = config.openai_base_url if isinstance(config, Settings) else config.base_url
        self.client = None if self.local_fallback else OpenAI(api_key=api_key, base_url=base_url)
        self.model = config.embedding_model
        self.dimensions = config.embedding_dimension
        self.batch_size = config.embedding_batch_size if isinstance(config, Settings) else 10

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if self.local_fallback:
            return [self._local_embedding(text) for text in texts]
        sanitized = [text[:20000] for text in texts]
        if self.client is None:
            raise RuntimeError("OpenAI client is not configured")
        vectors: list[list[float]] = []
        for start in range(0, len(sanitized), self.batch_size):
            batch = sanitized[start : start + self.batch_size]
            response = self.client.embeddings.create(
                model=self.model,
                input=batch,
                dimensions=self.dimensions,
            )
            vectors.extend(item.embedding for item in response.data)
        return vectors

    def _local_embedding(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        for idx in range(self.dimensions):
            byte = digest[idx % len(digest)]
            values.append((byte / 127.5) - 1.0)
        return values


class OpenAIChatModel:
    def __init__(self, config: Settings | OpenAICompatibleConfig) -> None:
        self.local_fallback = isinstance(config, Settings) and _use_local_fallback(config.openai_api_key)
        api_key = config.openai_api_key if isinstance(config, Settings) else config.api_key
        base_url = config.openai_base_url if isinstance(config, Settings) else config.base_url
        self.client = None if self.local_fallback else OpenAI(api_key=api_key, base_url=base_url)
        self.model = config.chat_model

    def complete(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        if self.local_fallback:
            return self._local_complete(messages)
        if self.client is None:
            raise RuntimeError("OpenAI client is not configured")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    def stream_complete(self, messages: list[dict[str, str]], temperature: float = 0.2):
        if self.local_fallback:
            yield self._local_complete(messages)
            return
        if self.client is None:
            raise RuntimeError("OpenAI client is not configured")
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                yield token

    def _local_complete(self, messages: list[dict[str, str]]) -> str:
        user_content = messages[-1]["content"] if messages else ""
        marker = "Context:\n"
        if marker not in user_content:
            return "没有在知识库中找到可引用的内容。"
        context = user_content.split(marker, 1)[1].split("\n\nQuestion:", 1)[0].strip()
        return context.split("\n\n---\n\n", 1)[0].strip() if context else "没有在知识库中找到可引用的内容。"


class OpenAICompatibleModelTester:
    def test(self, config: OpenAICompatibleConfig) -> dict:
        chat_result = self.test_chat(config)
        embedding_result = self.test_embedding(config)
        messages = [
            item
            for item in (chat_result.get("message"), embedding_result.get("message"))
            if item and item != "连接测试通过"
        ]
        chat_ok = bool(chat_result.get("chat_ok"))
        embedding_ok = bool(embedding_result.get("embedding_ok"))
        if chat_ok and embedding_ok:
            message = "连接测试通过"
        else:
            message = "；".join(messages) or "连接测试失败"
        return {
            "chat_ok": chat_ok,
            "embedding_ok": embedding_ok,
            "detected_dimension": embedding_result.get("detected_dimension"),
            "message": message,
        }

    def test_rerank(self, config: OpenAICompatibleConfig) -> dict:
        try:
            from app.integrations.reranker import RerankerClient

            results = RerankerClient(config).rerank(
                query="什么是文本排序模型",
                documents=[
                    "文本排序模型用于根据查询相关性对候选文档排序。",
                    "量子计算是计算科学的前沿领域。",
                ],
                top_n=1,
            )
            if not results:
                return {"rerank_ok": False, "message": "重排模型测试失败：未返回排序结果"}
            top_index, top_score = results[0]
            return {
                "rerank_ok": True,
                "top_index": top_index,
                "top_score": top_score,
                "message": "重排模型连接测试通过",
            }
        except Exception as exc:
            return {"rerank_ok": False, "message": f"重排模型测试失败: {exc}"}

    def test_chat(self, config: OpenAICompatibleConfig) -> dict:
        chat_ok = False
        messages: list[str] = []
        try:
            answer = OpenAIChatModel(config).complete(
                [
                    {"role": "system", "content": "你是 knowmate知友 的模型连通性测试助手。"},
                    {"role": "user", "content": "请只回复：连接正常"},
                ]
            )
            chat_ok = bool(answer.strip())
        except Exception as exc:
            messages.append(f"对话模型测试失败: {exc}")
        return {
            "chat_ok": chat_ok,
            "embedding_ok": True,
            "detected_dimension": None,
            "message": "连接测试通过" if chat_ok else "；".join(messages) or "连接测试失败",
        }

    def test_embedding(self, config: OpenAICompatibleConfig) -> dict:
        embedding_ok = False
        detected_dimension = None
        messages: list[str] = []
        try:
            vector = OpenAIEmbedder(config).embed("知友模型连接测试")
            detected_dimension = len(vector)
            embedding_ok = detected_dimension == config.embedding_dimension
            if not embedding_ok:
                messages.append(f"向量维度不匹配: 返回 {detected_dimension}, 配置 {config.embedding_dimension}")
        except Exception as exc:
            messages.append(f"向量模型测试失败: {exc}")
        return {
            "chat_ok": True,
            "embedding_ok": embedding_ok,
            "detected_dimension": detected_dimension,
            "message": "连接测试通过" if embedding_ok else "；".join(messages) or "连接测试失败",
        }
