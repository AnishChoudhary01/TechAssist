"""RAG business workflow: ingestion and semantic retrieval."""

from hashlib import sha256

from app.models.knowledge import DirectoryIngestionResult, IndexedDocument, IngestionResult, RetrievedChunk
from app.rag.chunking import TextChunker
from app.rag.documents import DocumentLoader
from app.rag.store import ChromaKnowledgeBase
from app.services.llm.ollama import OllamaEmbeddingClient


class KnowledgeBaseService:
    """Coordinates document loading, chunking, embedding, and vector search."""

    def __init__(
        self,
        loader: DocumentLoader,
        chunker: TextChunker,
        embedding_client: OllamaEmbeddingClient,
        store: ChromaKnowledgeBase,
    ) -> None:
        self._loader = loader
        self._chunker = chunker
        self._embedding_client = embedding_client
        self._store = store

    async def ingest_upload(self, filename: str, content: bytes, category: str | None) -> IngestionResult:
        pages = self._loader.load_bytes(filename, content)
        chunks = self._chunker.chunk(pages)
        if not chunks:
            raise ValueError("The document contains no indexable text.")
        document_id = self._document_id(filename, content)
        if self._store.has_document(document_id):
            return IngestionResult(source=filename, chunks_indexed=len(chunks))
        embeddings = await self._embedding_client.embed([chunk.content for chunk in chunks])
        self._store.upsert(chunks, embeddings, category, document_id)
        return IngestionResult(source=filename, chunks_indexed=len(chunks))

    async def ingest_directory(self, directory: str, category: str | None) -> DirectoryIngestionResult:
        pages = self._loader.load_directory(directory)
        chunks = self._chunker.chunk(pages)
        embeddings = await self._embedding_client.embed([chunk.content for chunk in chunks])
        # Directory ingestion has no original upload bytes; use its chunks to form
        # stable IDs while retaining the same persisted source-of-truth collection.
        for source in {chunk.source for chunk in chunks}:
            source_chunks = [chunk for chunk in chunks if chunk.source == source]
            source_embeddings = [embedding for chunk, embedding in zip(chunks, embeddings, strict=True) if chunk.source == source]
            self._store.upsert(source_chunks, source_embeddings, category, self._document_id(source, "".join(chunk.content for chunk in source_chunks).encode()))
        return DirectoryIngestionResult(
            files_indexed=len({page.source for page in pages}),
            chunks_indexed=len(chunks),
        )

    async def retrieve(self, query: str, limit: int) -> list[RetrievedChunk]:
        embedding = (await self._embedding_client.embed([query]))[0]
        return self._store.search(embedding, limit)

    def documents(self) -> list[IndexedDocument]:
        return self._store.documents()

    @staticmethod
    def _document_id(filename: str, content: bytes) -> str:
        return sha256(filename.encode("utf-8") + b"\0" + content).hexdigest()
