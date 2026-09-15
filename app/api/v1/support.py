"""Technical support question endpoints."""

from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.models.support import ModelOptionsResponse, ProcessingStep, SupportQuestion, SupportResponse
from app.services.orchestrator import (
    LLMServiceClient,
    RAGServiceClient,
    TechnicalSupportOrchestrator,
    UpstreamServiceError,
)
from app.services.guardrails import GuardrailService

router = APIRouter(prefix="/support", tags=["technical support"])


def get_support_service(settings: Settings = Depends(get_settings)) -> TechnicalSupportOrchestrator:
    """Compose the application orchestrator with the RAG and LLM service clients."""
    return TechnicalSupportOrchestrator(
        retriever=RAGServiceClient(settings),
        generator=LLMServiceClient(settings),
        guardrails=GuardrailService(settings.max_question_length, settings.rag_max_distance, settings.rag_min_context_characters),
    )


@router.get("/models", response_model=ModelOptionsResponse)
async def available_models(settings: Settings = Depends(get_settings)) -> ModelOptionsResponse:
    """Return the compact local models allowed for interactive selection."""
    return ModelOptionsResponse(default_model=settings.ollama_model, models=list(settings.ollama_models))


@router.post("/ask", response_model=SupportResponse, status_code=status.HTTP_200_OK)
async def ask_support_question(
    question: SupportQuestion,
    service: TechnicalSupportOrchestrator = Depends(get_support_service),
    settings: Settings = Depends(get_settings),
) -> SupportResponse:
    """Generate troubleshooting guidance for a user's technical-support question."""
    if question.model and question.model not in settings.ollama_models:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The selected model is not available.")
    started = perf_counter()
    try:
        if hasattr(service, "answer_with_metadata"):
            answer, model, sources, trace, decision, llm_called = await service.answer_with_metadata(question.question, question.model, question.use_rag)
        else:  # Compatibility with existing service doubles and integrations.
            answer, model, sources, trace = await service.answer(question.question, question.model, question.use_rag)
            from app.services.guardrails import GuardrailDecision
            decision, llm_called = GuardrailDecision(True, "ALLOWED"), True
    except UpstreamServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{error.service} failed: {error.detail}",
        ) from error

    total_duration = int((perf_counter() - started) * 1000)
    final_detail = (
        f"Guardrail rejected the request ({decision.category}); the LLM was not called."
        if not llm_called
        else ("Returned the grounded troubleshooting answer and its retrieved sources to the user."
        if question.use_rag
        else "Returned the direct LLM answer. Retrieval was not used."
        )
    )
    return SupportResponse(
        answer=answer,
        model=model,
        use_rag=question.use_rag,
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
                detail=final_detail,
                duration_ms=total_duration,
            ),
        ],
        guardrail_result=decision.category,
        llm_called=llm_called,
    )
