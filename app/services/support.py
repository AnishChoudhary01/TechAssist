"""Support use case orchestration.

This layer deliberately owns prompt construction rather than the HTTP route. In a
later exercise, retrieved knowledge-base context can be added here before calling
the language-model client.
"""

from app.services.llm.base import LanguageModelClient


SYSTEM_PROMPT = """You are TechAssist, a careful AI technical support assistant.
Give clear, safe, step-by-step troubleshooting advice. State assumptions, ask for
specific missing details when necessary, and do not invent commands, error codes,
or system state. Prefer reversible diagnostic steps before destructive actions."""


class TechnicalSupportService:
    """Coordinates the technical-support answer workflow."""

    def __init__(self, llm_client: LanguageModelClient) -> None:
        self._llm_client = llm_client

    async def answer(self, question: str) -> tuple[str, str]:
        """Return an LLM-generated answer and the model that produced it."""
        prompt = f"Technical support question:\n{question}\n\nProvide a helpful troubleshooting response."
        return await self._llm_client.generate(prompt=prompt, system_prompt=SYSTEM_PROMPT)

