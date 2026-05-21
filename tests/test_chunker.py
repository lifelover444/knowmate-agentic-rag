from app.rag.chunker import TextChunker


def test_chunker_creates_overlapping_chunks_with_offsets():
    chunker = TextChunker(chunk_size=10, chunk_overlap=3)

    chunks = chunker.split("0123456789abcdef")

    assert [chunk.content for chunk in chunks] == ["0123456789", "789abcdef"]
    assert [(chunk.start, chunk.end) for chunk in chunks] == [(0, 10), (7, 16)]
    assert [chunk.index for chunk in chunks] == [0, 1]


def test_chunker_drops_whitespace_only_input():
    chunker = TextChunker(chunk_size=10, chunk_overlap=3)

    assert chunker.split(" \n\t ") == []
