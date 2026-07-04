import re

LEGAL_NUMERAL = r"[一二三四五六七八九十百千万〇零两\d]+"

LAW_NAME_IN_BRACKETS_RE = re.compile(r"《([^》]{2,80}(?:法|典|条例|规定|办法|解释))》")
PLAIN_LAW_NAME_RE = re.compile(r"(中华人民共和国[\u4e00-\u9fff]{1,40}(?:法|典|条例|规定|办法))")
PART_RE = re.compile(rf"(第\s*{LEGAL_NUMERAL}\s*编\s*[^\n#]*)")
CHAPTER_RE = re.compile(rf"(第\s*{LEGAL_NUMERAL}\s*章\s*[^\n#]*)")
SECTION_RE = re.compile(rf"(第\s*{LEGAL_NUMERAL}\s*节\s*[^\n#]*)")
ARTICLE_RE = re.compile(rf"(?:第\s*)?(?P<num>{LEGAL_NUMERAL})\s*条(?:\s*之\s*(?P<suffix>{LEGAL_NUMERAL}))?")
STRUCTURE_MARKER_RE = re.compile(rf"第\s*{LEGAL_NUMERAL}\s*(?:编|章|节|条)")
KNOWLEDGE_PIECE_RE = re.compile(rf"第\s*(?P<num>{LEGAL_NUMERAL})\s*个知识片段")
ITEM_RE = re.compile(r"([（(][一二三四五六七八九十\d]+[）)])")
EXT_RE = re.compile(r"\.(pdf|docx?|md|markdown|txt)$", re.IGNORECASE)
DATE_SUFFIX_RE = re.compile(r"[_-]?\d{6,8}$")


def extract_legal_metadata(title: str | None, context_header: str | None, content: str | None) -> dict:
    haystack = "\n".join(item for item in (title, context_header, content) if item).strip()
    if not haystack:
        return {}
    law_haystack = _before_structure_marker(haystack)
    law_name = _first_match(LAW_NAME_IN_BRACKETS_RE, haystack) or _law_name_from_title(title) or _first_match(
        PLAIN_LAW_NAME_RE,
        law_haystack or haystack,
    )
    part = _clean_structure_heading(_last_match(PART_RE, context_header or "") or _first_match(PART_RE, content or ""))
    chapter = _clean_structure_heading(
        _last_match(CHAPTER_RE, context_header or "") or _first_match(CHAPTER_RE, content or "")
    )
    section = _clean_structure_heading(
        _last_match(SECTION_RE, context_header or "") or _first_match(SECTION_RE, content or "")
    )
    article_no = _first_article(content or "") or _last_article(context_header or "")
    item_no = _first_match(ITEM_RE, content or "")
    piece_index = _knowledge_piece_index(content or "")

    payload = {
        "law_name": law_name,
        "part": part,
        "chapter": chapter,
        "section": section,
        "article_no": article_no,
        "clause_no": None,
        "item_no": item_no,
        "knowledge_piece_index": piece_index,
    }
    cleaned = {key: value.strip() for key, value in payload.items() if isinstance(value, str) and value.strip()}
    if piece_index:
        cleaned["knowledge_piece_index"] = piece_index
    if not cleaned:
        return {}
    if cleaned.get("article_no"):
        cleaned["article_no_normalized"] = normalize_article_no(cleaned["article_no"])
    cleaned["legal_structure"] = True
    cleaned["legal_search_terms"] = " ".join(
        str(value)
        for key in (
            "law_name",
            "part",
            "chapter",
            "section",
            "article_no",
            "article_no_normalized",
            "item_no",
            "knowledge_piece_index",
        )
        if (value := cleaned.get(key))
    )
    return cleaned


def extract_legal_query_hints(query: str) -> dict:
    return extract_legal_metadata(None, None, query)


def build_legal_search_text(
    title: str | None,
    context_header: str | None,
    content: str | None,
    *,
    metadata: dict | None = None,
    generated_questions: list[dict[str, str]] | None = None,
) -> str:
    questions = [item["question"] for item in generated_questions or [] if item.get("question")]
    legal_terms = (metadata or {}).get("legal_search_terms")
    return "\n".join(item for item in (title, context_header, legal_terms, content, *questions) if item).strip()


def legal_match_score(query_hints: dict, hit_metadata: dict) -> float:
    if not query_hints or not hit_metadata:
        return 0.0
    score = 0.0
    if _same_value(query_hints.get("law_name"), hit_metadata.get("law_name")):
        score += 0.15
    if _same_article(query_hints.get("article_no"), hit_metadata.get("article_no")):
        score += 0.35
    if _same_value(query_hints.get("chapter"), hit_metadata.get("chapter")):
        score += 0.08
    if _same_value(query_hints.get("section"), hit_metadata.get("section")):
        score += 0.08
    if _same_value(query_hints.get("part"), hit_metadata.get("part")):
        score += 0.05
    return round(score, 4)


def normalize_article_no(value: str | None) -> str | None:
    parsed = _parse_article(value or "")
    if parsed is None:
        return None
    number, suffix = parsed
    if suffix is None:
        return str(number)
    return f"{number}-{suffix}"


def legal_article_variants(value: str | None) -> set[str]:
    cleaned = _compact(value)
    if not cleaned:
        return set()
    parsed = _parse_article(cleaned)
    if parsed is None:
        return {cleaned}
    number, suffix = parsed
    chinese_number = _int_to_chinese(number)
    base_variants = {f"第{chinese_number}条", f"第{number}条", f"{chinese_number}条", f"{number}条"}
    if suffix is None:
        return base_variants | {cleaned}
    chinese_suffix = _int_to_chinese(suffix)
    return {
        *(f"{base}之{chinese_suffix}" for base in base_variants),
        *(f"{base}之{suffix}" for base in base_variants),
        cleaned,
    }


def _law_name_from_title(title: str | None) -> str | None:
    if not title:
        return None
    stem = EXT_RE.sub("", title.strip())
    stem = DATE_SUFFIX_RE.sub("", stem)
    stem = stem.replace("_", " ").replace("-", " ").strip()
    if match := PLAIN_LAW_NAME_RE.search(stem):
        return match.group(1)
    compact = stem.split()[0] if stem.split() else stem
    if compact.startswith("中华人民共和国") and compact.endswith(("法", "典", "条例", "规定", "办法")):
        return compact
    return None


def _before_structure_marker(text: str) -> str:
    match = STRUCTURE_MARKER_RE.search(text or "")
    return text[: match.start()] if match else text


def _clean_structure_heading(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.split(r"(?:的)?核心|(?:的)?主要|适用条件|需要注意|例外|。|；|;|\n", value.strip(), maxsplit=1)[0]
    return re.sub(r"\s+", " ", cleaned).strip()


def _knowledge_piece_index(text: str) -> int | None:
    match = KNOWLEDGE_PIECE_RE.search(text or "")
    if not match:
        return None
    return _article_number_to_int(match.group("num"))


def _first_match(pattern: re.Pattern, text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _last_match(pattern: re.Pattern, text: str) -> str | None:
    matches = list(pattern.finditer(text or ""))
    return matches[-1].group(1).strip() if matches else None


def _same_value(left, right) -> bool:
    if not left or not right:
        return False
    return _compact(str(left)) == _compact(str(right))


def _same_article(left, right) -> bool:
    if not left or not right:
        return False
    left_normalized = normalize_article_no(str(left))
    right_normalized = normalize_article_no(str(right))
    if left_normalized and right_normalized:
        return left_normalized == right_normalized
    return _same_value(left, right)


def _first_article(text: str) -> str | None:
    match = ARTICLE_RE.search(text or "")
    return _format_article_match(match) if match else None


def _last_article(text: str) -> str | None:
    matches = list(ARTICLE_RE.finditer(text or ""))
    return _format_article_match(matches[-1]) if matches else None


def _format_article_match(match: re.Match | None) -> str | None:
    if match is None:
        return None
    number = _article_number_to_int(match.group("num"))
    if number is None:
        return _compact(match.group(0))
    article = f"第{_int_to_chinese(number)}条"
    suffix = match.groupdict().get("suffix")
    suffix_number = _article_number_to_int(suffix)
    if suffix_number is not None:
        article = f"{article}之{_int_to_chinese(suffix_number)}"
    return article


def _parse_article(value: str) -> tuple[int, int | None] | None:
    match = ARTICLE_RE.search(value or "")
    if not match:
        return None
    number = _article_number_to_int(match.group("num"))
    if number is None:
        return None
    suffix_number = _article_number_to_int(match.groupdict().get("suffix"))
    return number, suffix_number


def _article_number_to_int(value: str | None) -> int | None:
    cleaned = _compact(value)
    if not cleaned:
        return None
    if cleaned.isdigit():
        return int(cleaned)
    return _chinese_to_int(cleaned)


def _chinese_to_int(value: str) -> int | None:
    digits = {
        "零": 0,
        "〇": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    total = 0
    section = 0
    number = 0
    seen = False
    for char in value:
        if char in digits:
            number = digits[char]
            seen = True
            continue
        unit = units.get(char)
        if unit is None:
            return None
        seen = True
        if unit == 10000:
            section = (section + number) * unit
            total += section
            section = 0
        else:
            section += (number or 1) * unit
        number = 0
    if not seen:
        return None
    return total + section + number


def _int_to_chinese(value: int) -> str:
    if value <= 0:
        return str(value)
    digits = "零一二三四五六七八九"
    units = ["", "十", "百", "千"]
    if value >= 10000:
        high, low = divmod(value, 10000)
        prefix = f"{_int_to_chinese(high)}万"
        return prefix if low == 0 else f"{prefix}{_int_to_chinese(low)}"
    chars: list[str] = []
    zero_pending = False
    text = str(value)
    length = len(text)
    for index, char in enumerate(text):
        digit = int(char)
        unit_index = length - index - 1
        if digit == 0:
            zero_pending = bool(chars)
            continue
        if zero_pending:
            chars.append("零")
            zero_pending = False
        chars.append(digits[digit] + units[unit_index])
    result = "".join(chars)
    if result == "一十":
        return "十"
    if result.startswith("一十"):
        return result[1:]
    return result or "零"


def _compact(value: str | None) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())
