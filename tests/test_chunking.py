from app.rag.chunking import TextChunker
from app.rag.documents import DocumentPage


def test_chunker_creates_overlapping_chunks() -> None:
    chunks = TextChunker(chunk_size=30, overlap=10).chunk(
        [DocumentPage(content="one two three four five six seven eight nine ten", source="guide.txt")]
    )

    assert len(chunks) >= 2
    assert chunks[0].source == "guide.txt"
    assert set(chunks[0].content.split()) & set(chunks[1].content.split())
