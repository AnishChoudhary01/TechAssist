"""ChromaDB persistence adapter for technical-document chunks."""

from hashlib import sha256

import chromadb

from app.models.knowledge import RetrievedChunk
from app.rag.chunking import DocumentChunk


class ChromaKnowledgeBase:
    """Persist and retrieve chunks using precomputed Ollama embeddings."""

    def __init__(self, persist_directory: str, collection_name: str) -> None:
        self._client = chromadb.PersistentClient(path=persist_directory)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
        )

    def upsert(self, chunks: list[DocumentChunk], embeddings: list[list[float]], category: str | None) -> None:
        """Persist document chunks and their corresponding vectors."""
        if not chunks:
            return
        if len(chunks) != len(embeddings):
            raise ValueError("Each document chunk needs exactly one embedding.")

        ids = [self._chunk_id(chunk) for chunk in chunks]
        self._collection.upsert(
            ids=ids,
            documents=[chunk.content for chunk in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "source": chunk.source,
                    "page": chunk.page or 0,
                    "category": category or "",
                    "chunk_index": chunk.chunk_index,
                }
                for chunk in chunks
            ],
        )

    def search(self, query_embedding: list[float], limit: int) -> list[RetrievedChunk]:
        """Find the nearest chunks for a precomputed query embedding."""
        if self._collection.count() == 0:
            return []

        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(limit, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [
            RetrievedChunk(
                content=document,
                source=metadata.get("source", "unknown"),
                category=metadata.get("category") or None,
                page=metadata.get("page") or None,
                distance=distance,
            )
            for document, metadata, distance in zip(documents, metadatas, distances, strict=True)
        ]

    @staticmethod
    def _chunk_id(chunk: DocumentChunk) -> str:
        value = f"{chunk.source}:{chunk.page}:{chunk.chunk_index}:{chunk.content}"
        return sha256(value.encode("utf-8")).hexdigest()
