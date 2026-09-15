"""ChromaDB persistence adapter for technical-document chunks."""

from hashlib import sha256
from datetime import UTC, datetime

import chromadb

from app.models.knowledge import IndexedDocument, RetrievedChunk
from app.rag.chunking import DocumentChunk


class ChromaKnowledgeBase:
    """Persist and retrieve chunks using precomputed Ollama embeddings."""

    def __init__(self, persist_directory: str, collection_name: str) -> None:
        self._client = chromadb.PersistentClient(path=persist_directory)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
        )

    def upsert(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
        category: str | None,
        document_id: str | None = None,
    ) -> None:
        """Persist document chunks and their corresponding vectors."""
        if not chunks:
            return
        if len(chunks) != len(embeddings):
            raise ValueError("Each document chunk needs exactly one embedding.")

        document_id = document_id or sha256(chunks[0].source.encode("utf-8")).hexdigest()
        # A replacement with the same filename must not leave old chunks behind.
        # Content-addressed document IDs make re-uploading identical content idempotent.
        self._collection.delete(where={"source": chunks[0].source})
        indexed_at = datetime.now(UTC).isoformat()
        ids = [self._chunk_id(chunk, document_id) for chunk in chunks]
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
                    "document_id": document_id,
                    "indexed_at": indexed_at,
                }
                for chunk in chunks
            ],
        )

    def documents(self) -> list[IndexedDocument]:
        """Return document records reconstructed from the persisted collection."""
        result = self._collection.get(include=["metadatas"])
        records: dict[str, IndexedDocument] = {}
        for metadata in result.get("metadatas") or []:
            source = str(metadata.get("source", "unknown"))
            # Chroma collections created by earlier releases lack document_id.
            # Keep those persisted chunks visible and assign a stable legacy ID.
            document_id = str(metadata.get("document_id") or sha256(source.encode("utf-8")).hexdigest())
            record = records.get(document_id)
            if record is None:
                records[document_id] = IndexedDocument(
                    document_id=document_id,
                    filename=source,
                    status="indexed",
                    chunks_indexed=1,
                    category=metadata.get("category") or None,
                    indexed_at=metadata.get("indexed_at") or None,
                )
            else:
                records[document_id] = record.model_copy(update={"chunks_indexed": record.chunks_indexed + 1})
        return sorted(records.values(), key=lambda record: (record.indexed_at or "", record.filename), reverse=True)

    def has_document(self, document_id: str) -> bool:
        """Whether the exact content-addressed document has already been indexed."""
        return bool(self._collection.get(where={"document_id": document_id}, limit=1).get("ids"))

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
    def _chunk_id(chunk: DocumentChunk, document_id: str) -> str:
        value = f"{document_id}:{chunk.page}:{chunk.chunk_index}:{chunk.content}"
        return sha256(value.encode("utf-8")).hexdigest()
