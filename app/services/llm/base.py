"""Provider-neutral language model contract."""

from typing import Protocol


class LanguageModelClient(Protocol):
    """Contract implemented by an LLM provider adapter."""

    async def generate(self, prompt: str, system_prompt: str) -> tuple[str, str]:
        """Generate text and return it with the model identifier."""

