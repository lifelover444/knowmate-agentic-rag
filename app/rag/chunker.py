from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedChunk:
    content: str
    index: int
    start: int
    end: int


class TextChunker:
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 80) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, text: str) -> list[ParsedChunk]:
        normalized = text.strip()
        if not normalized:
            return []

        chunks: list[ParsedChunk] = []
        start = 0
        step = self.chunk_size - self.chunk_overlap
        while start < len(normalized):
            end = min(start + self.chunk_size, len(normalized))
            content = normalized[start:end].strip()
            if content:
                leading_trim = len(normalized[start:end]) - len(normalized[start:end].lstrip())
                trailing_trim = len(normalized[start:end]) - len(normalized[start:end].rstrip())
                chunks.append(
                    ParsedChunk(
                        content=content,
                        index=len(chunks),
                        start=start + leading_trim,
                        end=end - trailing_trim,
                    )
                )
            if end == len(normalized):
                break
            start += step
        return chunks
