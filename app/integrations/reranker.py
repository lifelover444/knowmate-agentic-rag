import httpx

from app.integrations.llm_openai import OpenAICompatibleConfig


class RerankerClient:
    def __init__(self, config: OpenAICompatibleConfig) -> None:
        self.config = config
        self.model = config.chat_model or config.embedding_model

    def rerank(self, *, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        response = httpx.post(
            f"{self.config.base_url.rstrip('/')}/rerank",
            headers={"Authorization": f"Bearer {self.config.api_key}"},
            json={"model": self.model, "query": query, "documents": documents, "top_n": top_n},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results") or []
        parsed = [
            (int(item["index"]), float(item.get("relevance_score", item.get("score", 0))))
            for item in results
            if "index" in item
        ]
        return sorted(parsed, key=lambda item: item[1], reverse=True)[:top_n]
