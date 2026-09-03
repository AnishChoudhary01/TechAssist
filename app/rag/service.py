"""RAG business workflow: ingestion and semantic retrieval."""

from app.models.knowledge import DirectoryIngestionResult, IngestionResult, RetrievedChunk
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
        embeddings = await self._embedding_client.embed([chunk.content for chunk in chunks])
        self._store.upsert(chunks, embeddings, category)
        return IngestionResult(source=filename, chunks_indexed=len(chunks))

    async def ingest_directory(self, directory: str, category: str | None) -> DirectoryIngestionResult:
        pages = self._loader.load_directory(directory)
        chunks = self._chunker.chunk(pages)
        embeddings = await self._embedding_client.embed([chunk.content for chunk in chunks])
        self._store.upsert(chunks, embeddings, category)
        return DirectoryIngestionResult(
            files_indexed=len({page.source for page in pages}),
            chunks_indexed=len(chunks),
        )

    async def retrieve(self, query: str, limit: int) -> list[RetrievedChunk]:
        embedding = (await self._embedding_client.embed([query]))[0]
        return self._store.search(embedding, limit)
