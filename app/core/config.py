"""Environment-based application settings."""

from dataclasses import dataclass
from functools import lru_cache
import os


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings for external services."""

    ollama_base_url: str
    ollama_model: str
    ollama_models: tuple[str, ...]
    ollama_timeout_seconds: float
    ollama_num_predict: int
    ollama_embedding_model: str
    rag_service_url: str
    llm_service_url: str
    chroma_persist_directory: str
    knowledge_base_directory: str
    rag_collection_name: str
    rag_top_k: int
    chunk_size: int
    chunk_overlap: int


@lru_cache
def get_settings() -> Settings:
    """Load settings from environment variables with local-development defaults."""
    default_model = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:0.5b-instruct")
    configured_models = tuple(
        model.strip()
        for model in os.getenv(
            "OLLAMA_MODELS",
            "qwen2.5-coder:0.5b-instruct,qwen2.5:0.5b,smollm2:360m",
        ).split(",")
        if model.strip()
    )
    # Keep the configured default selectable even when a custom list omits it.
    model_options = configured_models if default_model in configured_models else (default_model, *configured_models)

    return Settings(
        # Explicit IPv4 loopback avoids localhost/IPv6 resolution mismatches on Windows.
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
        ollama_model=default_model,
        ollama_models=model_options,
        # A cold local model request can take several minutes on CPU-only machines.
        ollama_timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "300")),
        ollama_num_predict=int(os.getenv("OLLAMA_NUM_PREDICT", "256")),
        ollama_embedding_model=os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
        rag_service_url=os.getenv("RAG_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/"),
        llm_service_url=os.getenv("LLM_SERVICE_URL", "http://127.0.0.1:8002").rstrip("/"),
        chroma_persist_directory=os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_data"),
        knowledge_base_directory=os.getenv("KNOWLEDGE_BASE_DIRECTORY", "./data/knowledge_base"),
        rag_collection_name=os.getenv("RAG_COLLECTION_NAME", "techassist_knowledge"),
        rag_top_k=int(os.getenv("RAG_TOP_K", "4")),
        chunk_size=int(os.getenv("CHUNK_SIZE", "1000")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "150")),
    )
