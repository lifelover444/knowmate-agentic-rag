from dataclasses import dataclass

from app.rag.prompt import build_quick_answer_messages


@dataclass(frozen=True)
class AnswerSource:
    document_id: str
    knowledge_base_id: str
    chunk_id: str
    content: str
    score: float
    title: str | None = None


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    sources: list[AnswerSource]


class QuickAnswerEngine:
    def __init__(self, embedder, chat_model, vector_store) -> None:
        self.embedder = embedder
        self.chat_model = chat_model
        self.vector_store = vector_store

    def answer(self, *, knowledge_base_id: str, query: str, top_k: int) -> AnswerResult:
        query_vector = self.embedder.embed(query)
        hits = self.vector_store.search(knowledge_base_id=knowledge_base_id, query_vector=query_vector, limit=top_k)
        if not hits:
            return AnswerResult(answer="没有在知识库中找到可引用的内容。", sources=[])

        sources = [
            AnswerSource(
                document_id=hit["knowledge_id"],
                knowledge_base_id=hit["knowledge_base_id"],
                chunk_id=hit["chunk_id"],
                content=hit["content"],
                score=float(hit["score"]),
                title=hit.get("title"),
            )
            for hit in hits
        ]
        messages = build_quick_answer_messages(query=query, contexts=[source.content for source in sources])
        return AnswerResult(answer=self.chat_model.complete(messages), sources=sources)
