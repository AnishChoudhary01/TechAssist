"""Semantic retrieval endpoint exposed by the RAG service."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.knowledge import get_knowledge_base_service
from app.models.knowledge import RetrievalRequest, RetrievalResponse
from app.rag.service import KnowledgeBaseService
from app.services.llm.ollama import OllamaConnectionError, OllamaResponseError

router = APIRouter(prefix="/v1", tags=["retrieval"])


@router.post("/retrieve", response_model=RetrievalResponse)
async def retrieve_context(
    request: RetrievalRequest,
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> RetrievalResponse:
    """Embed a support question and return its nearest indexed knowledge chunks."""
    try:
        results = await service.retrieve(request.query, request.limit)
    except OllamaConnectionError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Ollama embedding service is unavailable.") from error
    except OllamaResponseError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Ollama returned invalid embeddings.") from error
    return RetrievalResponse(results=results)
