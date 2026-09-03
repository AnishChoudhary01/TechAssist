"""Technical support question endpoints."""

from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.models.support import ProcessingStep, SupportQuestion, SupportResponse
from app.services.orchestrator import (
    LLMServiceClient,
    RAGServiceClient,
    TechnicalSupportOrchestrator,
    UpstreamServiceError,
)

router = APIRouter(prefix="/support", tags=["technical support"])


def get_support_service(settings: Settings = Depends(get_settings)) -> TechnicalSupportOrchestrator:
    """Compose the application orchestrator with the RAG and LLM service clients."""
    return TechnicalSupportOrchestrator(
        retriever=RAGServiceClient(settings),
        generator=LLMServiceClient(settings),
    )


@router.post("/ask", response_model=SupportResponse, status_code=status.HTTP_200_OK)
async def ask_support_question(
    question: SupportQuestion,
    service: TechnicalSupportOrchestrator = Depends(get_support_service),
) -> SupportResponse:
    """Generate troubleshooting guidance for a user's technical-support question."""
    started = perf_counter()
    try:
        answer, model, sources, trace = await service.answer(question.question)
    except UpstreamServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{error.service} failed: {error.detail}",
        ) from error

    total_duration = int((perf_counter() - started) * 1000)
    return SupportResponse(
        answer=answer,
        model=model,
        sources=sources,
        processing_trace=[
            ProcessingStep(
                stage="User question received",
                service="API service",
                detail=f"Received a {len(question.question)}-character technical support question.",
            ),
            *trace,
            ProcessingStep(
                stage="Final response returned",
                service="API service",
                detail="Returned the grounded troubleshooting answer and its retrieved sources to the user.",
                duration_ms=total_duration,
            ),
        ],
    )
