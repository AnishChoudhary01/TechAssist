import asyncio

from app.models.knowledge import RetrievedChunk
from app.services.orchestrator import TechnicalSupportOrchestrator


class StubRetriever:
    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        assert query == "Why does setup fail?"
        return [RetrievedChunk(content="Verify the configuration file.", source="install.md")]


class StubGenerator:
    async def generate(self, prompt: str, system_prompt: str) -> tuple[str, str]:
        assert "Verify the configuration file." in prompt
        assert "Why does setup fail?" in prompt
        assert "TechAssist" in system_prompt
        return "Check the configuration file.", "codellama:7b"


def test_orchestrator_retrieves_context_before_generation() -> None:
    answer, model, sources, trace = asyncio.run(
        TechnicalSupportOrchestrator(StubRetriever(), StubGenerator()).answer("Why does setup fail?")
    )

    assert answer == "Check the configuration file."
    assert model == "codellama:7b"
    assert sources[0].source == "install.md"
    assert [step.stage for step in trace] == [
        "Knowledge base / RAG retrieval",
        "Relevant context assembled",
        "Ollama / Code Llama generation",
    ]
