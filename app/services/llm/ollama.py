"""Ollama adapter for the configured local technical-support model."""

import httpx

from app.core.config import Settings


class OllamaConnectionError(Exception):
    """Raised when the Ollama service cannot be reached."""


class OllamaResponseError(Exception):
    """Raised when Ollama returns an unusable response."""


class OllamaEmbeddingClient:
    """Calls Ollama's embedding endpoint using a dedicated embedding model."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.ollama_base_url
        self._model = settings.ollama_embedding_model
        self._timeout_seconds = settings.ollama_timeout_seconds

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed one or more text values with Ollama's `/api/embed` endpoint."""
        if not texts:
            return []

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds, trust_env=False) as client:
                response = await client.post(
                    f"{self._base_url}/api/embed",
                    json={"model": self._model, "input": texts},
                )
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise OllamaConnectionError(f"Ollama embedding request timed out after {self._timeout_seconds:g} seconds.") from error
        except httpx.HTTPStatusError as error:
            raise OllamaConnectionError(_ollama_http_error(error)) from error
        except httpx.RequestError as error:
            raise OllamaConnectionError(f"Could not connect to Ollama embedding endpoint: {type(error).__name__}.") from error

        try:
            embeddings = response.json()["embeddings"]
            if len(embeddings) != len(texts) or not all(embedding for embedding in embeddings):
                raise ValueError("Unexpected embedding count or empty vector.")
            return embeddings
        except (KeyError, TypeError, ValueError) as error:
            raise OllamaResponseError from error


class OllamaCodeLlamaClient:
    """Calls Ollama's non-streaming generate endpoint."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.ollama_base_url
        self._model = settings.ollama_model
        self._timeout_seconds = settings.ollama_timeout_seconds
        self._num_predict = settings.ollama_num_predict

    async def generate(self, prompt: str, system_prompt: str) -> tuple[str, str]:
        """Request a troubleshooting answer from the configured Ollama model."""
        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "keep_alive": "10m",
            "options": {"num_predict": self._num_predict, "temperature": 0.2},
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds, trust_env=False) as client:
                response = await client.post(f"{self._base_url}/api/generate", json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise OllamaConnectionError(f"Ollama generation timed out after {self._timeout_seconds:g} seconds.") from error
        except httpx.HTTPStatusError as error:
            raise OllamaConnectionError(_ollama_http_error(error)) from error
        except httpx.RequestError as error:
            raise OllamaConnectionError(f"Could not connect to Ollama generation endpoint: {type(error).__name__}.") from error

        try:
            data = response.json()
            answer = data["response"].strip()
            model = data.get("model", self._model)
        except (KeyError, TypeError, ValueError) as error:
            raise OllamaResponseError from error

        if not answer:
            raise OllamaResponseError("Ollama returned an empty response.")

        return answer, model


def _ollama_http_error(error: httpx.HTTPStatusError) -> str:
    """Return the useful part of an Ollama HTTP failure for an API response."""
    try:
        detail = error.response.json().get("error", error.response.text)
    except ValueError:
        detail = error.response.text
    return f"Ollama returned HTTP {error.response.status_code}: {str(detail).replace(chr(10), ' ')[:300]}"
