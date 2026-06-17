import json

DEFAULT_QUERY_INTENT = "kb_search"


def build_query_rewrite_messages(history: list[dict[str, str]], query: str) -> list[dict[str, str]]:
    return build_query_understand_messages(history, query)


def build_query_understand_messages(
    history: list[dict[str, str]],
    query: str,
    *,
    language: str = "中文",
) -> list[dict[str, str]]:
    history_text = "\n".join(f"{item['role']}: {item['content']}" for item in history[-8:])
    return [
        {
            "role": "system",
            "content": (
                "你是 knowmate 知友的 Query Understand 助手，需要完成问题改写和意图分类。\n"
                "任务：\n"
                "1. 将用户问题改写为可独立用于知识库检索的 query，补全指代和省略信息。\n"
                "2. 保留实体、专有名词、法律/技术关键词和核心检索词。\n"
                "3. 禁止输出“请在知识库中查找”“请搜索”等元指令，只输出实际检索问题。\n"
                "4. 意图只能是 kb_search、web_search、greeting、chitchat、follow_up、"
                "image_only、doc_only、summarize、clarification 之一；不确定时使用 kb_search。\n"
                f"5. rewrite_query 必须使用{language}。\n\n"
                "必须只输出单个 JSON 对象，不要 markdown、代码块或解释。\n"
                'JSON schema: {"rewrite_query":"string","intent":"string","image_description":"string"}'
            ),
        },
        {
            "role": "user",
            "content": (
                "## Conversation History\n"
                f"{history_text or '<empty />'}\n\n"
                "## User Question\n"
                f"{query}\n\n"
                "## JSON Output"
            ),
        },
    ]


def parse_query_understand_output(raw: str) -> dict:
    content = (raw or "").strip()
    if not content:
        return {
            "rewrite_query": None,
            "intent": DEFAULT_QUERY_INTENT,
            "image_description": "",
            "structured": False,
        }
    parsed = _parse_json_object(content)
    if parsed is None:
        return {
            "rewrite_query": None,
            "intent": DEFAULT_QUERY_INTENT,
            "image_description": "",
            "structured": False,
        }
    rewrite_query = _first_string_field(parsed, "rewrite_query", "rewritten_query", "query", "question")
    intent = _first_string_field(parsed, "intent") or DEFAULT_QUERY_INTENT
    image_description = _first_string_field(
        parsed,
        "image_description",
        "image_desc",
        "image_text",
        "image_ocr_text",
        "description",
    )
    return {
        "rewrite_query": rewrite_query.strip() or None,
        "intent": intent.strip() or DEFAULT_QUERY_INTENT,
        "image_description": image_description.strip(),
        "structured": True,
    }


def _parse_json_object(content: str) -> dict | None:
    for candidate in _json_candidates(content):
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _json_candidates(content: str) -> list[str]:
    candidates = [content]
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        candidate = content[start : end + 1]
        if candidate != content:
            candidates.append(candidate)
    return candidates


def _first_string_field(payload: dict, *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""
