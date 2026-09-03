"""Data models shared by knowledge-base ingestion and RAG retrieval."""

from pathlib import Path

from pydantic import BaseModel, Field


class IngestionResult(BaseModel):
    """Summary of a completed knowledge-base ingestion operation."""

    source: str
    chunks_indexed: int


class DirectoryIngestionResult(BaseModel):
    """Summary for a directory-wide ingestion operation."""

    files_indexed: int
    chunks_indexed: int


class RetrievalRequest(BaseModel):
    """A query supplied to the RAG service."""

    query: str = Field(min_length=3, max_length=4_000)
    limit: int = Field(default=4, ge=1, le=10)


class RetrievedChunk(BaseModel):
    """A semantically relevant knowledge-base excerpt."""

    content: str
    source: str
    category: str | None = None
    page: int | None = None
    distance: float | None = None


class RetrievalResponse(BaseModel):
    """Relevant excerpts returned by a vector similarity search."""

    results: list[RetrievedChunk]


def source_name(file_name: str) -> str:
    """Return only the final filename for untrusted upload names."""
    return Path(file_name).name
