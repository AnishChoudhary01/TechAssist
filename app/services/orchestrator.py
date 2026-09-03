"""Application-layer orchestration across the RAG and LLM services."""

from time import perf_counter
from typing import Protocol

import httpx

from app.core.config import Settings
from app.models.knowledge import RetrievedChunk, RetrievalResponse
from app.models.llm import GenerationResponse
from app.models.support import ProcessingStep


SYSTEM_PROMPT = """You are TechAssist, a careful AI technical support assistant.
Give clear, safe, step-by-step troubleshooting advice. Use supplied reference
context when it is relevant. Do not claim the context says something it does not,
and do not invent commands, error codes, or system state. Prefer reversible
diagnostic steps before destructive actions."""


class UpstreamServiceError(Exception):
    """Raised when a dependent internal service cannot complete a request."""

    def __init__(self, service: str, detail: str) -> None:
        self.service = service
        self.detail = detail
        super().__init__(f"{service}: {detail}")


class ContextRetriever(Protocol):
    async def retrieve(self, query: str) -> list[RetrievedChunk]: ...


class ResponseGenerator(Protocol):
    async def generate(self, prompt: str, system_prompt: str) -> tuple[str, str]: ...


class RAGServiceClient:
    """HTTP client for the independent RAG service."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.rag_service_url
        self._timeout = settings.ollama_timeout_seconds
        self._top_k = settings.rag_top_k

    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout, trust_env=False) as client:
                response = await client.post(
                    f"{self._base_url}/v1/retrieve",
                    json={"query": query, "limit": self._top_k},
                )
                response.raise_for_status()
            return RetrievalResponse.model_validate(response.json()).results
        except httpx.HTTPStatusError as error:
            raise UpstreamServiceError(
                "RAG service",
                f"returned HTTP {error.response.status_code}: {_response_detail(error.response)}",
            ) from error
        except httpx.RequestError as error:
            raise UpstreamServiceError("RAG service", f"connection failed: {error}") from error
        except ValueError as error:
            raise UpstreamServiceError("RAG service", f"returned an invalid payload: {error}") from error


class LLMServiceClient:
    """HTTP client for the independent Code Llama service."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.llm_service_url
        self._timeout = settings.ollama_timeout_seconds

    async def generate(self, prompt: str, system_prompt: str) -> tuple[str, str]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout, trust_env=False) as client:
                response = await client.post(
                    f"{self._base_url}/v1/generate",
                    json={"prompt": prompt, "system_prompt": system_prompt},
                )
                response.raise_for_status()
            parsed = GenerationResponse.model_validate(response.json())
            return parsed.answer, parsed.model
        except httpx.HTTPStatusError as error:
            raise UpstreamServiceError(
                "LLM service",
                f"returned HTTP {error.response.status_code}: {_response_detail(error.response)}",
            ) from error
        except httpx.RequestError as error:
            raise UpstreamServiceError("LLM service", f"connection failed: {error}") from error
        except ValueError as error:
            raise UpstreamServiceError("LLM service", f"returned an invalid payload: {error}") from error


def _response_detail(response: httpx.Response) -> str:
    """Extract a short, safe diagnostic from an internal FastAPI error response."""
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text
    return str(detail).replace("\n", " ")[:300]


class TechnicalSupportOrchestrator:
    """Retrieve relevant context, then request a grounded LLM answer."""

    def __init__(self, retriever: ContextRetriever, generator: ResponseGenerator) -> None:
        self._retriever = retriever
        self._generator = generator

    async def answer(self, question: str) -> tuple[str, str, list[RetrievedChunk], list[ProcessingStep]]:
        """Retrieve context, generate an answer, and record the processing trace."""
        retrieval_started = perf_counter()
        sources = await self._retriever.retrieve(question)
        retrieval_duration = int((perf_counter() - retrieval_started) * 1000)
        context = self._format_context(sources)
        prompt = (
            f"Technical support question:\n{question}\n\n"
            f"Knowledge-base context:\n{context}\n\n"
            "Provide a helpful troubleshooting response in at most 250 words. If the supplied context is insufficient, say what to check next."
        )
        generation_started = perf_counter()
        answer, model = await self._generator.generate(prompt, SYSTEM_PROMPT)
        generation_duration = int((perf_counter() - generation_started) * 1000)
        source_labels = sorted({source.source for source in sources})
        trace = [
            ProcessingStep(
                stage="Knowledge base / RAG retrieval",
                service="RAG service",
                detail=(
                    f"Embedded the question and searched ChromaDB; retrieved {len(sources)} relevant chunk(s)"
                    + (f" from {', '.join(source_labels)}." if source_labels else ".")
                ),
                duration_ms=retrieval_duration,
            ),
            ProcessingStep(
                stage="Relevant context assembled",
                service="API orchestrator",
                detail="Added retrieved chunks to the grounded troubleshooting prompt.",
            ),
            ProcessingStep(
                stage="Ollama / Code Llama generation",
                service="LLM service",
                detail=f"Generated the troubleshooting response with {model} through Ollama.",
                duration_ms=generation_duration,
            ),
        ]
        return answer, model, sources, trace

    @staticmethod
    def _format_context(sources: list[RetrievedChunk]) -> str:
        if not sources:
            return "No relevant indexed context was found. Use general troubleshooting knowledge and state uncertainty."
        return "\n\n".join(
            f"[Source: {source.source}{f', page {source.page}' if source.page else ''}]\n{source.content}"
            for source in sources
        )
