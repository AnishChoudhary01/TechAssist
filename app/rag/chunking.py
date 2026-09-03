"""Text chunking for vector indexing."""

from dataclasses import dataclass

from app.rag.documents import DocumentPage


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    content: str
    source: str
    page: int | None
    chunk_index: int


class TextChunker:
    """Split documents into overlapping, mostly sentence-preserving character chunks."""

    def __init__(self, chunk_size: int, overlap: int) -> None:
        if overlap >= chunk_size:
            raise ValueError("Chunk overlap must be smaller than chunk size.")
        self._chunk_size = chunk_size
        self._overlap = overlap

    def chunk(self, pages: list[DocumentPage]) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for page in pages:
            text = " ".join(page.content.split())
            start = 0
            index = 0
            while start < len(text):
                end = min(start + self._chunk_size, len(text))
                if end < len(text):
                    break_at = text.rfind(" ", start + self._chunk_size // 2, end)
                    if break_at > start:
                        end = break_at
                chunk_text = text[start:end].strip()
                if chunk_text:
                    chunks.append(
                        DocumentChunk(
                            content=chunk_text,
                            source=page.source,
                            page=page.page,
                            chunk_index=index,
                        )
                    )
                    index += 1
                if end >= len(text):
                    break
                start = max(end - self._overlap, start + 1)
        return chunks
