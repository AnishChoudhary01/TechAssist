import asyncio

import httpx
import pytest

from app.core.config import Settings
from app.services.orchestrator import LLMServiceClient, UpstreamServiceError


def test_llm_client_reports_the_internal_service_error(monkeypatch) -> None:
    class FailingClient:
        def __init__(self, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def post(self, *args, **kwargs) -> httpx.Response:
            request = httpx.Request("POST", "http://llm.example/v1/generate")
            return httpx.Response(503, json={"detail": "Ollama generation service is unavailable."}, request=request)

    monkeypatch.setattr(httpx, "AsyncClient", FailingClient)
    settings = Settings(
        ollama_base_url="http://ollama",
        ollama_model="codellama:7b",
        ollama_timeout_seconds=300,
        ollama_num_predict=256,
        ollama_embedding_model="nomic-embed-text",
        rag_service_url="http://rag",
        llm_service_url="http://llm.example",
        chroma_persist_directory="./chroma",
        knowledge_base_directory="./knowledge",
        rag_collection_name="knowledge",
        rag_top_k=4,
        chunk_size=1000,
        chunk_overlap=150,
    )

    with pytest.raises(UpstreamServiceError, match="Ollama generation service is unavailable") as error:
        asyncio.run(LLMServiceClient(settings).generate("prompt", "system"))

    assert error.value.service == "LLM service"
