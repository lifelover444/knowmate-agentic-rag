def build_query_rewrite_messages(history: list[dict[str, str]], query: str) -> list[dict[str, str]]:
    history_text = "\n".join(f"{item['role']}: {item['content']}" for item in history[-8:])
    return [
        {
            "role": "system",
            "content": (
                "你是 knowmate知友 的检索 query 改写助手。请基于历史对话，把用户追问改写成"
                "可独立用于知识库检索的中文 query。只输出改写后的 query，不要解释。"
            ),
        },
        {"role": "user", "content": f"历史对话:\n{history_text}\n\n当前问题:\n{query}"},
    ]
