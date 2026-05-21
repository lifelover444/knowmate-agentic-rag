def build_quick_answer_messages(query: str, contexts: list[str]) -> list[dict[str, str]]:
    context_text = "\n\n---\n\n".join(contexts)
    return [
        {
            "role": "system",
            "content": (
                "You are knowmate知友, a precise RAG assistant. Answer only from the provided context. "
                "If the context is insufficient, say that the knowledge base does not contain enough information."
            ),
        },
        {
            "role": "user",
            "content": f"Context:\n{context_text}\n\nQuestion:\n{query}",
        },
    ]
