import asyncio

from app.models.knowledge import RetrievedChunk
from app.services.orchestrator import TechnicalSupportOrchestrator


class StubRetriever:
    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        assert query == "Why does setup fail?"
        return [RetrievedChunk(content="Verify the configuration file.", source="install.md")]


class StubGenerator:
    async def generate(self, prompt: str, system_prompt: str, model: str | None = None) -> tuple[str, str]:
        assert "Verify the configuration file." in prompt
        assert "Why does setup fail?" in prompt
        assert "TechAssist" in system_prompt
        return "Check the configuration file.", model or "qwen2.5-coder:0.5b-instruct"


class DirectGenerator:
    async def generate(self, prompt: str, system_prompt: str, model: str | None = None) -> tuple[str, str]:
        assert "Why does setup fail?" in prompt
        assert "Knowledge-base context:" not in prompt
        assert "TechAssist" in system_prompt
        return "Check the configuration file.", model or "qwen2.5-coder:0.5b-instruct"


def test_orchestrator_retrieves_context_before_generation() -> None:
    answer, model, sources, trace = asyncio.run(
        TechnicalSupportOrchestrator(StubRetriever(), StubGenerator()).answer("Why does setup fail?")
    )

    assert answer == "Check the configuration file."
    assert model == "qwen2.5-coder:0.5b-instruct"
    assert sources[0].source == "install.md"
    assert [step.stage for step in trace] == [
        "Knowledge base / RAG retrieval",
        "Relevant chunks selected",
        "Relevant context assembled",
        "Ollama / LLM generation",
    ]


class FailingRetriever:
    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        raise AssertionError("Retrieval must not run when RAG is off.")


def test_orchestrator_skips_retrieval_when_rag_is_off() -> None:
    answer, model, sources, trace = asyncio.run(
        TechnicalSupportOrchestrator(FailingRetriever(), DirectGenerator()).answer("Why does setup fail?", use_rag=False)
    )

    assert answer == "Check the configuration file."
    assert sources == []
    assert model == "qwen2.5-coder:0.5b-instruct"
    assert "RAG mode is off" in trace[0].detail
    assert [step.stage for step in trace] == [
        "Knowledge base / RAG retrieval",
        "Relevant chunks selected",
        "Relevant context assembled",
        "Ollama / LLM generation",
    ]
