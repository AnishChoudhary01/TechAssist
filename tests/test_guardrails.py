import asyncio

import pytest

from app.models.knowledge import RetrievedChunk
from app.services.guardrails import GuardrailService, EMPTY_INPUT, INSUFFICIENT_KNOWLEDGE, OUT_OF_SCOPE, TOO_LONG
from app.services.orchestrator import TechnicalSupportOrchestrator
from app.services.guardrail_evaluation import _output_checks, load_guardrail_questions


def test_input_guardrail_categories_are_deterministic() -> None:
    guardrails = GuardrailService(40, 1.0, 20)
    assert guardrails.validate_input("Who is the president of India?").category == OUT_OF_SCOPE
    assert guardrails.validate_input("...").category == EMPTY_INPUT
    assert guardrails.validate_input("How do I troubleshoot a Python error?" * 2).category == TOO_LONG
    assert guardrails.validate_retrieval([]).category == INSUFFICIENT_KNOWLEDGE


@pytest.mark.parametrize("question", [
    "how to reboot my laptop",
    "how to connect to Wi-Fi",
    "my laptop is running slowly",
    "how do I update Windows",
    "how do I fix a printer connection",
    "my computer is not starting",
])
def test_normal_device_support_questions_are_in_scope(question: str) -> None:
    assert GuardrailService(2000, 1.0, 20).validate_input(question).allowed is True


@pytest.mark.parametrize("question", [
    "write me a poem",
    "who is the president of India",
    "tell me a joke",
    "what is today's cricket score",
    "plan my vacation",
])
def test_unrelated_questions_remain_out_of_scope(question: str) -> None:
    decision = GuardrailService(2000, 1.0, 20).validate_input(question)
    assert decision.allowed is False
    assert decision.category == OUT_OF_SCOPE


class NoCallRetriever:
    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        raise AssertionError("rejected input must not reach retrieval")


class NoCallGenerator:
    async def generate(self, prompt: str, system_prompt: str, model: str | None = None) -> tuple[str, str]:
        raise AssertionError("rejected request must not reach the LLM")


class SupportRetriever:
    def __init__(self) -> None:
        self.called = False

    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        self.called = True
        return [RetrievedChunk(content="Restart the laptop from the Start menu, then reconnect to Wi-Fi.", source="laptop-guide.md", distance=0.2)]


class SupportGenerator:
    def __init__(self) -> None:
        self.called = False

    async def generate(self, prompt: str, system_prompt: str, model: str | None = None) -> tuple[str, str]:
        self.called = True
        return "Restart the laptop, then verify the wireless connection.", "test-model"


def test_valid_device_support_question_reaches_rag_and_llm() -> None:
    retriever = SupportRetriever()
    generator = SupportGenerator()
    service = TechnicalSupportOrchestrator(retriever, generator, GuardrailService(2000, 1.0, 20))

    _, _, _, _, decision, llm_called = asyncio.run(service.answer_with_metadata("How do I reboot my laptop?"))

    assert decision.category == "ALLOWED"
    assert retriever.called is True
    assert generator.called is True
    assert llm_called is True


def test_out_of_scope_input_stops_before_llm() -> None:
    service = TechnicalSupportOrchestrator(NoCallRetriever(), NoCallGenerator(), GuardrailService(2000, 1.0, 20))
    answer, model, sources, trace, decision, llm_called = asyncio.run(service.answer_with_metadata("Write a romantic poem."))
    assert decision.category == OUT_OF_SCOPE
    assert llm_called is False
    assert model == "not-called"
    assert sources == []
    assert "technical-support" in answer
    assert trace[0].stage == "Input guardrail"


class WeakRetriever:
    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        return [RetrievedChunk(content="short", source="tiny.md", distance=2.0)]


def test_weak_rag_context_allows_valid_support_question_to_reach_llm() -> None:
    generator = SupportGenerator()
    service = TechnicalSupportOrchestrator(WeakRetriever(), generator, GuardrailService(2000, 1.0, 80))
    _, _, _, trace, decision, llm_called = asyncio.run(service.answer_with_metadata("How do I configure a Python application?"))
    assert decision.category == "ALLOWED"
    assert llm_called is True
    assert generator.called is True
    assert any(step.stage == "RAG sufficiency guardrail" for step in trace)


def test_output_criteria_require_refusal_when_knowledge_is_insufficient() -> None:
    case = {"question": "How do I configure an unsupported feature?", "expected_answerable": False}
    checks = _output_checks(case, "I don't have enough information in the knowledge base to answer this reliably.", [], False)
    assert all(checks.values())
    assert len(load_guardrail_questions(50)) == 17
