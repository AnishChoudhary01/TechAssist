import asyncio

import pytest

from app.rag.chunking import TextChunker
from app.rag.documents import DocumentLoader
from app.rag.service import KnowledgeBaseService


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[1.0] for _ in texts]


class FakePersistentStore:
    def __init__(self) -> None:
        self.records: dict[str, tuple[list, str | None]] = {}

    def has_document(self, document_id: str) -> bool:
        return document_id in self.records

    def upsert(self, chunks, embeddings, category, document_id) -> None:
        self.records[document_id] = (chunks, category)

    def documents(self):
        return []


def test_upload_is_persisted_once_and_identical_reupload_is_idempotent() -> None:
    embeddings = FakeEmbeddingClient()
    store = FakePersistentStore()
    service = KnowledgeBaseService(DocumentLoader(), TextChunker(1000, 150), embeddings, store)

    first = asyncio.run(service.ingest_upload("guide.txt", b"Restart the service after changing its configuration.", "installation"))
    second = asyncio.run(service.ingest_upload("guide.txt", b"Restart the service after changing its configuration.", "installation"))

    assert first.chunks_indexed == second.chunks_indexed == 1
    assert len(store.records) == 1
    assert embeddings.calls == 1


def test_empty_document_is_not_marked_indexed() -> None:
    embeddings = FakeEmbeddingClient()
    store = FakePersistentStore()
    service = KnowledgeBaseService(DocumentLoader(), TextChunker(1000, 150), embeddings, store)

    with pytest.raises(ValueError, match="no indexable text"):
        asyncio.run(service.ingest_upload("empty.txt", b"   ", None))

    assert not store.records
    assert embeddings.calls == 0
