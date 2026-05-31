import httpx

from app.integrations.llm_openai import OpenAICompatibleConfig


class RerankerClient:
    def __init__(self, config: OpenAICompatibleConfig) -> None:
        self.config = config
        self.model = config.chat_model or config.embedding_model

    def rerank(self, *, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        url = self._endpoint_url()
        request_json = self._request_json(query=query, documents=documents, top_n=top_n)
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {self.config.api_key}"},
            json=request_json,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results") or payload.get("output", {}).get("results") or []
        parsed = [
            (int(item["index"]), float(item.get("relevance_score", item.get("score", 0))))
            for item in results
            if "index" in item
        ]
        return sorted(parsed, key=lambda item: item[1], reverse=True)[:top_n]

    def _endpoint_url(self) -> str:
        base_url = self.config.base_url.rstrip("/")
        if base_url.endswith(("/rerank", "/reranks", "/text-rerank")):
            return base_url
        return f"{base_url}/rerank"

    def _request_json(self, *, query: str, documents: list[str], top_n: int) -> dict:
        if self.model == "qwen3-rerank":
            return {
                "model": self.model,
                "query": query,
                "documents": documents,
                "top_n": top_n,
            }
        if self.config.provider == "qwen":
            return {
                "model": self.model,
                "input": {"query": query, "documents": documents},
                "parameters": {"top_n": top_n},
            }
        return {"model": self.model, "query": query, "documents": documents, "top_n": top_n}
