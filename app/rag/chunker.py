import math
import re
from dataclasses import dataclass, field
from typing import Literal

StrategyTier = Literal["heading", "heuristic", "legacy"]
LANG_ENGLISH = "en"
LANG_GERMAN = "de"
LANG_CHINESE = "zh"
LANG_MIXED = "mixed"
CHARS_PER_TOKEN = {
    LANG_ENGLISH: 4.0,
    LANG_GERMAN: 4.5,
    LANG_CHINESE: 1.7,
    LANG_MIXED: 3.0,
}


@dataclass(frozen=True)
class ChunkingConfig:
    chunk_size: int = 512
    chunk_overlap: int = 80
    separators: list[str] = field(default_factory=lambda: ["\n\n", "\n", "。"])
    strategy: str = "auto"
    token_limit: int = 0
    languages: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedChunk:
    content: str
    index: int
    start: int
    end: int
    context_header: str = ""
    images: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def embedding_content(self) -> str:
        body = self.content.strip()
        return f"{self.context_header}\n\n{body}" if self.context_header else body


@dataclass(frozen=True)
class DocProfile:
    total_chars: int = 0
    total_lines: int = 0
    avg_line_len: float = 0
    std_line_len: float = 0
    md_heading_counts: dict[int, int] = field(default_factory=dict)
    md_heading_total: int = 0
    numbered_section_count: int = 0
    all_caps_short_line_count: int = 0
    blank_paragraph_breaks: int = 0
    form_feed_count: int = 0
    visual_sep_count: int = 0
    german_chapter_count: int = 0
    english_chapter_count: int = 0
    chinese_chapter_count: int = 0
    repeated_footer_count: int = 0
    has_tables: bool = False
    has_code: bool = False
    code_ratio: float = 0
    detected_langs: list[str] = field(default_factory=list)

    def heading_density(self) -> float:
        return self.md_heading_total / self.total_lines if self.total_lines else 0

    def dominant_heading_level(self) -> int:
        for level in range(1, 7):
            if self.md_heading_counts.get(level, 0) >= 3:
                return level
        for level in range(6, 0, -1):
            if self.md_heading_counts.get(level, 0) > 0:
                return level
        return 0

    def heuristic_marker_total(self) -> int:
        return (
            self.numbered_section_count
            + self.all_caps_short_line_count
            + self.form_feed_count
            + self.visual_sep_count
            + self.german_chapter_count
            + self.english_chapter_count
            + self.chinese_chapter_count
        )

    def to_dict(self) -> dict:
        return {
            "total_chars": self.total_chars,
            "total_lines": self.total_lines,
            "avg_line_len": round(self.avg_line_len, 2),
            "std_line_len": round(self.std_line_len, 2),
            "md_heading_counts": {str(key): value for key, value in self.md_heading_counts.items()},
            "md_heading_total": self.md_heading_total,
            "numbered_section_count": self.numbered_section_count,
            "all_caps_short_line_count": self.all_caps_short_line_count,
            "blank_paragraph_breaks": self.blank_paragraph_breaks,
            "form_feed_count": self.form_feed_count,
            "visual_sep_count": self.visual_sep_count,
            "german_chapter_count": self.german_chapter_count,
            "english_chapter_count": self.english_chapter_count,
            "chinese_chapter_count": self.chinese_chapter_count,
            "repeated_footer_count": self.repeated_footer_count,
            "has_tables": self.has_tables,
            "has_code": self.has_code,
            "code_ratio": round(self.code_ratio, 4),
            "detected_langs": self.detected_langs,
        }


@dataclass(frozen=True)
class TierRejection:
    tier: StrategyTier
    reason: str


@dataclass(frozen=True)
class ChunkingDiagnostics:
    selected_tier: StrategyTier
    tier_chain: list[StrategyTier]
    rejected: list[TierRejection]
    profile: DocProfile
    token_limit_applied: bool = False
    token_limit_reason: str = ""
    requested_chunk_size: int = 0
    effective_chunk_size: int = 0
    fallback_tier: StrategyTier | None = None


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str = ""


@dataclass(frozen=True)
class ChildChunk:
    chunk: ParsedChunk
    parent_index: int

    @property
    def context_header(self) -> str:
        return self.chunk.context_header


@dataclass(frozen=True)
class ParentChildResult:
    parents: list[ParsedChunk] = field(default_factory=list)
    children: list[ChildChunk] = field(default_factory=list)


PROTECTED_PATTERN_SPECS = [
    ("formula", re.compile(r"(?s)\$\$.*?\$\$")),
    ("image", re.compile(r"!\[[^\]]*]\([^)]+\)")),
    ("markdown_link", re.compile(r"\[[^\]]+]\([^)]+\)")),
    (
        "table",
        re.compile(
            r"(?m)[ ]*(?:\|[^|\n]*)+\|[\r\n]+\s*(?:\|\s*:?-{3,}:?\s*)+\|[\r\n]+(?:[ ]*(?:\|[^|\n]*)+\|[\r\n]*)*"
        ),
    ),
    ("code", re.compile(r"(?s)```(?:\w+)?[\r\n].*?```")),
]
PROTECTED_PATTERNS = [pattern for _, pattern in PROTECTED_PATTERN_SPECS]
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
NUMBERED_RE = re.compile(r"^\s*((\d+(\.\d+){0,4})|([一二三四五六七八九十]+[、.．]))\s+.+")
CHINESE_CHAPTER_RE = re.compile(r"^\s*第[一二三四五六七八九十百千万\d]+[章节条部分]\s*.+")
ENGLISH_CHAPTER_RE = re.compile(r"^\s*(chapter|section)\s+\d+[:.\s].+", re.IGNORECASE)
GERMAN_CHAPTER_RE = re.compile(r"^\s*(kapitel|abschnitt)\s+\d+[:.\s].+", re.IGNORECASE)
VISUAL_SEP_RE = re.compile(r"^\s*[-=_*]{3,}\s*$")


class AdaptiveTextChunker:
    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self.requested_config = config or ChunkingConfig()
        self.config = ensure_defaults(self.requested_config)
        self.token_limit_applied, self.token_limit_reason = token_limit_diagnostics(
            self.requested_config,
            self.config,
        )

    def split(self, text: str) -> list[ParsedChunk]:
        chunks, _ = self.split_with_diagnostics(text)
        return chunks

    def split_with_diagnostics(self, text: str) -> tuple[list[ParsedChunk], ChunkingDiagnostics]:
        normalized = text.strip()
        profile = profile_document(normalized)
        chain = resolve_strategy_chain(profile, self.config.strategy)
        rejected: list[TierRejection] = []
        last: tuple[StrategyTier, list[ParsedChunk]] | None = None
        for tier in chain:
            chunks = run_tier(tier, normalized, self.config, profile)
            result = validate_chunks(chunks, len(normalized), self.config.chunk_size)
            if result.ok:
                return chunks, self._diagnostics(tier, chain, rejected, profile)
            rejected.append(TierRejection(tier, result.reason))
            last = (tier, chunks)
        tier, chunks = last if last else ("legacy", split_legacy(normalized, self.config))
        return chunks, self._diagnostics(tier, chain, rejected, profile)

    def _diagnostics(
        self,
        tier: StrategyTier,
        chain: list[StrategyTier],
        rejected: list[TierRejection],
        profile: DocProfile,
    ) -> ChunkingDiagnostics:
        return ChunkingDiagnostics(
            selected_tier=tier,
            tier_chain=chain,
            rejected=rejected,
            profile=profile,
            token_limit_applied=self.token_limit_applied,
            token_limit_reason=self.token_limit_reason,
            requested_chunk_size=self.requested_config.chunk_size or 512,
            effective_chunk_size=self.config.chunk_size,
            fallback_tier=tier if rejected else None,
        )


class TextChunker:
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 80) -> None:
        self.chunker = AdaptiveTextChunker(
            ChunkingConfig(strategy="legacy", chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        )

    def split(self, text: str) -> list[ParsedChunk]:
        return self.chunker.split(text)


def ensure_defaults(config: ChunkingConfig) -> ChunkingConfig:
    chunk_size = config.chunk_size or 512
    if config.token_limit and config.token_limit > 0:
        language = config_language(config.languages)
        token_budget_chars = chars_for_token_limit(config.token_limit, language)
        chunk_size = min(chunk_size, max(50, token_budget_chars))
    overlap = config.chunk_overlap
    if overlap < 0:
        overlap = 0
    if overlap >= chunk_size:
        overlap = chunk_size // 2
    return ChunkingConfig(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=config.separators or ["\n\n", "\n", "。"],
        strategy=config.strategy or "legacy",
        token_limit=config.token_limit or 0,
        languages=config.languages or [],
    )


def config_language(languages: list[str]) -> str:
    for language in languages or []:
        normalized = language.lower().strip()
        if normalized in CHARS_PER_TOKEN:
            return normalized
    return LANG_MIXED


def chars_for_token_limit(tokens: int, language: str) -> int:
    if tokens <= 0:
        return 0
    ratio = CHARS_PER_TOKEN.get(language, CHARS_PER_TOKEN[LANG_MIXED])
    return int(tokens * ratio * 0.9)


def approx_token_count(text: str, language: str = LANG_MIXED) -> int:
    if not text:
        return 0
    ratio = CHARS_PER_TOKEN.get(language, CHARS_PER_TOKEN[LANG_MIXED])
    approx = len(text) / ratio
    return max(1, int(approx + 0.5))


def detect_language(sample: str) -> str:
    if not sample:
        return LANG_MIXED
    cjk = latin = umlaut = 0
    for char in sample:
        if "\u4e00" <= char <= "\u9fff" or "\u3040" <= char <= "\u30ff" or "\uac00" <= char <= "\ud7af":
            cjk += 1
        elif char in "äöüÄÖÜß":
            umlaut += 1
            latin += 1
        elif char.isascii() and char.isalpha():
            latin += 1
    total = cjk + latin
    if total == 0:
        return LANG_MIXED
    cjk_ratio = cjk / total
    latin_ratio = latin / total
    if cjk_ratio >= 0.15 and latin_ratio >= 0.15:
        return LANG_MIXED
    if cjk_ratio > 0.3:
        return LANG_CHINESE
    if umlaut > 0 or has_german_words(sample):
        return LANG_GERMAN
    return LANG_ENGLISH


def has_german_words(sample: str) -> bool:
    text = f" {sample[:512].lower()} "
    return any(word in text for word in (" der ", " die ", " das ", " und ", " ist ", " nicht ", " mit ", " auf "))


def token_limit_diagnostics(requested: ChunkingConfig, effective: ChunkingConfig) -> tuple[bool, str]:
    if not requested.token_limit or requested.token_limit <= 0:
        return False, ""
    requested_size = requested.chunk_size or 512
    if effective.chunk_size >= requested_size:
        return False, ""
    language = config_language(requested.languages)
    return (
        True,
        (
            f"token_limit={requested.token_limit} language={language} "
            f"clamped chunk_size {requested_size}->{effective.chunk_size}"
        ),
    )


def profile_document(text: str) -> DocProfile:
    if not text:
        return DocProfile(md_heading_counts={}, detected_langs=[])
    lines = text.splitlines()
    lengths = [len(line) for line in lines]
    heading_counts: dict[int, int] = {}
    md_heading_total = 0
    numbered = all_caps = visual = german = english = chinese = 0
    for line in lines:
        stripped = line.strip()
        if match := HEADING_RE.match(stripped):
            level = len(match.group(1))
            heading_counts[level] = heading_counts.get(level, 0) + 1
            md_heading_total += 1
            continue
        numbered += int(bool(NUMBERED_RE.match(stripped)))
        german += int(bool(GERMAN_CHAPTER_RE.match(stripped)))
        english += int(bool(ENGLISH_CHAPTER_RE.match(stripped)))
        chinese += int(bool(CHINESE_CHAPTER_RE.match(stripped)))
        visual += int(bool(VISUAL_SEP_RE.match(stripped)))
        all_caps += int(stripped.isupper() and 3 <= len(stripped) <= 80)
    avg = sum(lengths) / len(lengths) if lengths else 0
    variance = sum((length - avg) ** 2 for length in lengths) / len(lengths) if lengths else 0
    code_len = sum(end - start for start, end in _protected_spans(text, patterns=[PROTECTED_PATTERNS[-1]]))
    return DocProfile(
        total_chars=len(text),
        total_lines=len(lines),
        avg_line_len=avg,
        std_line_len=math.sqrt(variance),
        md_heading_counts=heading_counts,
        md_heading_total=md_heading_total,
        numbered_section_count=numbered,
        all_caps_short_line_count=all_caps,
        blank_paragraph_breaks=text.count("\n\n\n"),
        form_feed_count=text.count("\f"),
        visual_sep_count=visual,
        german_chapter_count=german,
        english_chapter_count=english,
        chinese_chapter_count=chinese,
        repeated_footer_count=0,
        has_tables="| ---" in text or "|---" in text,
        has_code="```" in text,
        code_ratio=code_len / len(text) if text else 0,
            detected_langs=[_detect_language(text[:4096])],
    )


def protected_block_stats(text: str) -> dict[str, int]:
    stats = {name: 0 for name, _ in PROTECTED_PATTERN_SPECS}
    spans: list[tuple[int, int]] = []
    for name, pattern in PROTECTED_PATTERN_SPECS:
        for match in pattern.finditer(text):
            if name == "markdown_link" and match.start() > 0 and text[match.start() - 1] == "!":
                continue
            stats[name] += 1
            spans.append(match.span())
    merged_spans = _merge_spans(spans)
    stats["total"] = sum(stats[name] for name, _ in PROTECTED_PATTERN_SPECS)
    stats["total_chars"] = sum(end - start for start, end in merged_spans)
    return stats


def resolve_strategy_chain(profile: DocProfile, strategy: str) -> list[StrategyTier]:
    if strategy == "heading":
        return ["heading", "legacy"]
    if strategy == "heuristic":
        return ["heuristic", "legacy"]
    if strategy in {"legacy", "recursive", ""}:
        return ["legacy"]
    chain: list[StrategyTier] = []
    if profile.md_heading_total >= 3 and profile.heading_density() > 0.005 and profile.dominant_heading_level() > 0:
        chain.append("heading")
    if profile.heuristic_marker_total() >= 3 or profile.form_feed_count > 0:
        chain.append("heuristic")
    chain.append("legacy")
    return chain


def run_tier(tier: StrategyTier, text: str, config: ChunkingConfig, profile: DocProfile) -> list[ParsedChunk]:
    if tier == "heading":
        return split_heading(text, config, profile)
    if tier == "heuristic":
        return split_heuristic(text, config)
    return split_legacy(text, config)


def validate_chunks(chunks: list[ParsedChunk], total_chars: int, chunk_size: int) -> ValidationResult:
    if not chunks:
        return ValidationResult(False, "no chunks produced")
    if len(chunks) == 1 and total_chars > 2 * chunk_size:
        return ValidationResult(False, "single chunk for large document")
    lengths = [len(chunk.content) for chunk in chunks]
    tiny = sum(1 for length in lengths[:-1] if length < 50)
    if total_chars > chunk_size * 3 and tiny > len(chunks) / 4 and tiny > 2:
        return ValidationResult(False, "too many tiny chunks")
    if max(lengths) < chunk_size / 4 and total_chars > chunk_size * 3:
        return ValidationResult(False, "all chunks far below target size")
    if max(lengths) > 2 * chunk_size and chunk_size > 0:
        return ValidationResult(False, "chunk exceeds 2x target size")
    return ValidationResult(True)


def split_heading(text: str, config: ChunkingConfig, profile: DocProfile) -> list[ParsedChunk]:
    level = profile.dominant_heading_level()
    if level == 0:
        return split_legacy(text, config)
    lines = text.splitlines(keepends=True)
    boundaries: list[tuple[int, str]] = [(0, "")]
    offset = 0
    for line in lines:
        stripped = line.strip()
        match = HEADING_RE.match(stripped)
        if match and len(match.group(1)) <= level and offset != 0:
            boundaries.append((offset, stripped))
        offset += len(line)
    if len(boundaries) <= 1:
        return split_legacy(text, config)

    headings = HeadingHierarchy()
    all_headings = [(match.start(), match.group(0).strip()) for match in re.finditer(r"(?m)^#{1,6}\s+.+$", text)]
    chunks: list[ParsedChunk] = []
    for index, (start, line) in enumerate(boundaries):
        end = boundaries[index + 1][0] if index + 1 < len(boundaries) else len(text)
        for heading_start, heading_line in all_headings:
            if heading_start <= start and (line == "" or heading_start >= start):
                headings.observe(heading_line)
        if line:
            headings.observe(line)
        breadcrumb = headings.breadcrumb()
        section = text[start:end]
        if len(breadcrumb) + 2 + len(section) <= config.chunk_size:
            chunks.append(_make_chunk(section, len(chunks), start, end, breadcrumb))
        else:
            inner = split_legacy(section, config)
            for chunk in inner:
                chunks.append(
                    ParsedChunk(
                        content=chunk.content,
                        index=len(chunks),
                        start=start + chunk.start,
                        end=start + chunk.end,
                        context_header=breadcrumb,
                        metadata=chunk.metadata,
                    )
                )
    return chunks


def split_heuristic(text: str, config: ChunkingConfig) -> list[ParsedChunk]:
    boundaries = _heuristic_boundaries(text)
    if not boundaries:
        return split_legacy(text, config)
    if boundaries[0] != 0:
        boundaries.insert(0, 0)
    if boundaries[-1] != len(text):
        boundaries.append(len(text))
    chunks: list[ParsedChunk] = []
    start = boundaries[0]
    current_end = start
    min_chunk_size = max(50, config.chunk_size // 4)
    for next_end in boundaries[1:]:
        block_len = next_end - current_end
        if block_len > config.chunk_size:
            if current_end - start > 0:
                chunks.append(_make_chunk(text[start:current_end], len(chunks), start, current_end))
            chunks.extend(_reindex(split_legacy(text[current_end:next_end], config), len(chunks), current_end))
            start = next_end
            current_end = next_end
            continue
        if next_end - start > config.chunk_size and current_end - start >= min_chunk_size:
            chunks.append(_make_chunk(text[start:current_end], len(chunks), start, current_end))
            start = _aligned_overlap_start(text, current_end, config.chunk_overlap)
        current_end = next_end
    if current_end > start:
        chunks.append(_make_chunk(text[start:current_end], len(chunks), start, current_end))
    return chunks or split_legacy(text, config)


def split_legacy(text: str, config: ChunkingConfig) -> list[ParsedChunk]:
    if not text.strip():
        return []
    protected = _protected_spans(text)
    units = _build_units(text, protected, config.separators, config.chunk_size)
    return _merge_units(units, config.chunk_size, config.chunk_overlap)


def split_parent_child(text: str, parent_config: ChunkingConfig, child_config: ChunkingConfig) -> ParentChildResult:
    parents = AdaptiveTextChunker(parent_config).split(text)
    children: list[ChildChunk] = []
    child_index = 0
    for parent_index, parent in enumerate(parents):
        parent_children = AdaptiveTextChunker(child_config).split(parent.content)
        for child in parent_children:
            context = _merge_context(parent.context_header, child.context_header)
            children.append(
                ChildChunk(
                    chunk=ParsedChunk(
                        content=child.content,
                        index=child_index,
                        start=parent.start + child.start,
                        end=parent.start + child.end,
                        context_header=context,
                        metadata=child.metadata,
                    ),
                    parent_index=parent_index,
                )
            )
            child_index += 1
    return ParentChildResult(parents=parents, children=children)


class HeadingHierarchy:
    def __init__(self) -> None:
        self._items: dict[int, str] = {}

    def observe(self, line: str) -> None:
        match = HEADING_RE.match(line.strip())
        if not match:
            return
        level = len(match.group(1))
        self._items[level] = line.strip()
        for existing in list(self._items):
            if existing > level:
                self._items.pop(existing)

    def breadcrumb(self) -> str:
        return "\n".join(self._items[level] for level in sorted(self._items))


def _protected_spans(text: str, patterns: list[re.Pattern] | None = None) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pattern in patterns or PROTECTED_PATTERNS:
        spans.extend(match.span() for match in pattern.finditer(text))
    return _merge_spans(spans)


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    spans.sort()
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if not merged or start >= merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _build_units(
    text: str, protected: list[tuple[int, int]], separators: list[str], chunk_size: int
) -> list[tuple[str, int, int]]:
    units: list[tuple[str, int, int]] = []
    cursor = 0
    for start, end in protected:
        if start > cursor:
            units.extend(_split_with_offsets(text[cursor:start], cursor, separators, chunk_size))
        units.append((text[start:end], start, end))
        cursor = end
    if cursor < len(text):
        units.extend(_split_with_offsets(text[cursor:], cursor, separators, chunk_size))
    return [unit for unit in units if unit[0]]


def _split_with_offsets(text: str, base: int, separators: list[str], chunk_size: int) -> list[tuple[str, int, int]]:
    parts = _split_by_separators(text, separators, chunk_size)
    units = []
    cursor = 0
    for part in parts:
        idx = text.find(part, cursor)
        if idx < 0:
            idx = cursor
        start = base + idx
        end = start + len(part)
        units.append((part, start, end))
        cursor = idx + len(part)
    return units


def _split_by_separators(text: str, separators: list[str], chunk_size: int) -> list[str]:
    if not text or not separators or len(text) <= chunk_size:
        return [text]
    for index, sep in enumerate(separators):
        if not sep or sep not in text:
            continue
        raw = re.split(f"({re.escape(sep)})", text)
        pieces = [raw[i] + (raw[i + 1] if i + 1 < len(raw) else "") for i in range(0, len(raw), 2)]
        out: list[str] = []
        remaining = separators[index + 1 :]
        for piece in pieces:
            if len(piece) > chunk_size and remaining:
                out.extend(_split_by_separators(piece, remaining, chunk_size))
            else:
                out.append(piece)
        return [piece for piece in out if piece]
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def _merge_units(units: list[tuple[str, int, int]], chunk_size: int, chunk_overlap: int) -> list[ParsedChunk]:
    chunks: list[ParsedChunk] = []
    current: list[tuple[str, int, int]] = []
    current_len = 0
    for unit in units:
        text, start, end = unit
        unit_len = len(text)
        if current and current_len + unit_len > chunk_size:
            chunks.append(_chunk_from_units(current, len(chunks)))
            current = _compute_overlap(current, chunk_overlap, chunk_size, unit_len)
            current_len = sum(len(item[0]) for item in current)
        if unit_len > max(7500, chunk_size * 2):
            if current:
                chunks.append(_chunk_from_units(current, len(chunks)))
                current = []
                current_len = 0
            for offset in range(start, end, chunk_size):
                piece = text[offset - start : offset - start + chunk_size]
                chunks.append(_make_chunk(piece, len(chunks), offset, offset + len(piece)))
        else:
            current.append(unit)
            current_len += unit_len
    if current:
        chunks.append(_chunk_from_units(current, len(chunks)))
    return chunks


def _compute_overlap(
    current: list[tuple[str, int, int]], chunk_overlap: int, chunk_size: int, next_len: int
) -> list[tuple[str, int, int]]:
    if chunk_overlap <= 0:
        return []
    kept: list[tuple[str, int, int]] = []
    total = 0
    for unit in reversed(current):
        text = unit[0]
        if total + len(text) > chunk_overlap or total + len(text) + next_len > chunk_size:
            break
        kept.insert(0, unit)
        total += len(text)
    while kept and _is_separator_only(kept[0][0]):
        kept.pop(0)
    return kept


def _chunk_from_units(units: list[tuple[str, int, int]], index: int) -> ParsedChunk:
    content = "".join(unit[0] for unit in units)
    return _make_chunk(content, index, units[0][1], units[-1][2])


def _make_chunk(content: str, index: int, start: int, end: int, context_header: str = "") -> ParsedChunk:
    leading = len(content) - len(content.lstrip())
    trailing = len(content) - len(content.rstrip())
    return ParsedChunk(
        content=content.strip(),
        index=index,
        start=start + leading,
        end=end - trailing,
        context_header=context_header,
    )


def _heuristic_boundaries(text: str) -> list[int]:
    boundaries: list[int] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if (
            "\f" in line
            or NUMBERED_RE.match(stripped)
            or CHINESE_CHAPTER_RE.match(stripped)
            or ENGLISH_CHAPTER_RE.match(stripped)
            or GERMAN_CHAPTER_RE.match(stripped)
            or VISUAL_SEP_RE.match(stripped)
        ):
            boundaries.append(offset)
        offset += len(line)
    return sorted(set(boundary for boundary in boundaries if boundary >= 0))


def _aligned_overlap_start(text: str, end: int, overlap: int) -> int:
    if overlap <= 0:
        return end
    candidate = max(0, end - overlap)
    for pos in range(candidate, end):
        if text[pos] in "\n。.!?！？":
            return pos + 1
    return candidate


def _reindex(chunks: list[ParsedChunk], base_index: int, offset: int) -> list[ParsedChunk]:
    return [
        ParsedChunk(
            content=chunk.content,
            index=base_index + index,
            start=offset + chunk.start,
            end=offset + chunk.end,
            context_header=chunk.context_header,
            metadata=chunk.metadata,
        )
        for index, chunk in enumerate(chunks)
    ]


def _merge_context(parent: str, child: str) -> str:
    if not parent:
        return child
    if not child:
        return parent
    lines = parent.splitlines()
    child_lines = child.splitlines()
    if lines and child_lines and lines[-1] == child_lines[0]:
        child_lines = child_lines[1:]
    return "\n".join([*lines, *child_lines])


def _is_separator_only(text: str) -> bool:
    return all(char.isspace() or char == "。" for char in text)


def _detect_language(sample: str) -> str:
    return detect_language(sample)
