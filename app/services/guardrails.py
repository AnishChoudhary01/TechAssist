"""Deterministic, testable admission and RAG-sufficiency guardrails."""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.models.knowledge import RetrievedChunk


OUT_OF_SCOPE = "OUT_OF_SCOPE"
EMPTY_INPUT = "EMPTY_OR_MEANINGLESS"
TOO_LONG = "INPUT_TOO_LONG"
INSUFFICIENT_KNOWLEDGE = "INSUFFICIENT_KNOWLEDGE"
ALLOWED = "ALLOWED"

_OUT_OF_SCOPE_PATTERNS = re.compile(
    r"\b(president|election|politics?|cricket|football|score|romantic poem|poem|joke|recipe|"
    r"horoscope|medical diagnosis|vacation|travel itinerary)\b",
    re.IGNORECASE,
)
# This is deliberately a domain classifier, not a phrase allowlist.  It covers
# the support subjects users normally ask about: applications and services as
# well as devices, operating systems, connectivity, and peripherals.
_TECHNICAL_SUPPORT_TERMS = re.compile(
    r"\b(error|install|setup|configure|configuration|python|database|server|service|start|app(?:lication)?|"
    r"module|package|login|network|code|api|feature|bug|fail(?:s|ed|ure)?|exception|support|"
    r"troubleshoot|document|knowledge base|rag|system|computer|pc|laptop|desktop|windows|mac(?:os)?|"
    r"linux|reboot|restart|boot|startup|shut ?down|update|upgrade|slow|performance|freeze|crash|"
    r"wi-?fi|wireless|internet|connection|connect|printer|print(?:ing)?|keyboard|mouse|screen|"
    r"display|monitor|driver|bluetooth|browser|email|password|account|file|folder|disk|storage)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GuardrailDecision:
    allowed: bool
    category: str
    response: str | None = None


class GuardrailService:
    def __init__(self, max_question_length: int, rag_max_distance: float, rag_min_context_characters: int) -> None:
        self.max_question_length = max_question_length
        self.rag_max_distance = rag_max_distance
        self.rag_min_context_characters = rag_min_context_characters

    def validate_input(self, question: str) -> GuardrailDecision:
        cleaned = question.strip()
        if len(cleaned) < 3 or not re.search(r"[A-Za-z0-9]", cleaned):
            return GuardrailDecision(False, EMPTY_INPUT, "Please enter a clear technical-support question.")
        if len(cleaned) > self.max_question_length:
            return GuardrailDecision(False, TOO_LONG, f"Please shorten your technical-support question to {self.max_question_length} characters or fewer.")
        # Explicit non-support topics win even if they happen to mention a
        # device.  Everything else needs a genuine technical-support signal.
        if _OUT_OF_SCOPE_PATTERNS.search(cleaned) or not _TECHNICAL_SUPPORT_TERMS.search(cleaned):
            return GuardrailDecision(False, OUT_OF_SCOPE, "I can only help with questions related to the technical-support knowledge available in this application.")
        return GuardrailDecision(True, ALLOWED)

    def validate_retrieval(self, sources: list[RetrievedChunk]) -> GuardrailDecision:
        useful = [source for source in sources if source.content.strip() and (source.distance is None or source.distance <= self.rag_max_distance)]
        context_size = sum(len(source.content.strip()) for source in useful)
        if not useful or context_size < self.rag_min_context_characters:
            return GuardrailDecision(False, INSUFFICIENT_KNOWLEDGE, "I don't have enough information in the knowledge base to answer this reliably.")
        return GuardrailDecision(True, ALLOWED)
