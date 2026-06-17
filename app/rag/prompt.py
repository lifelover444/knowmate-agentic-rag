def build_quick_answer_messages(
    query: str,
    contexts: list[str],
    system_prompt: str | None = None,
    conversation_context: str | None = None,
    attachments_context: str | None = None,
) -> list[dict[str, str]]:
    context_parts = []
    if contexts:
        context_parts.append("\n\n---\n\n".join(contexts))
    if attachments_context:
        context_parts.append(attachments_context)
    context_text = "\n\n---\n\n".join(context_parts)
    history_section = f"Conversation history:\n{conversation_context}\n\n" if conversation_context else ""
    return [
        {
            "role": "system",
            "content": system_prompt
            or (
                "You are knowmate知友, a precise RAG assistant. Answer only from the provided context. "
                "When the context contains applicable rules, apply those rules to the user's facts and explain the "
                "reasoning; do not say the knowledge base is insufficient merely because the user's facts are not "
                "repeated verbatim in the context. If the context is missing the rule needed for a sub-question, say "
                "that this specific part is not covered by the knowledge base. Answer in the user's language."
            ),
        },
        {
            "role": "user",
            "content": f"{history_section}Context:\n{context_text}\n\nQuestion:\n{query}",
        },
    ]
