"""Generation endpoint exposed by the dedicated LLM service."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.models.llm import GenerationRequest, GenerationResponse
from app.services.llm.ollama import OllamaCodeLlamaClient, OllamaConnectionError, OllamaResponseError

router = APIRouter(prefix="/v1", tags=["generation"])


def get_llm_client(settings: Settings = Depends(get_settings)) -> OllamaCodeLlamaClient:
    """Create the configured Ollama model adapter used only by the LLM service."""
    return OllamaCodeLlamaClient(settings)


@router.post("/generate", response_model=GenerationResponse)
async def generate_response(
    request: GenerationRequest,
    client: OllamaCodeLlamaClient = Depends(get_llm_client),
    settings: Settings = Depends(get_settings),
) -> GenerationResponse:
    """Generate a response through the configured Ollama model."""
    if request.model and request.model not in settings.ollama_models:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The selected model is not available.")
    try:
        answer, model = await client.generate(request.prompt, request.system_prompt, request.model)
    except OllamaConnectionError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Ollama generation service is unavailable.") from error
    except OllamaResponseError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Ollama returned an invalid response.") from error
    return GenerationResponse(answer=answer, model=model)
