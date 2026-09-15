"""Endpoints for controlled, persistent TechAssist model evaluation."""

import asyncio
from dataclasses import dataclass
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.models.evaluation import EvaluationRunRequest, EvaluationRunStarted, EvaluationStatus
from app.services.evaluation import METRIC_DEFINITIONS, latest_results, load_questions, run_evaluation
from app.services.guardrail_evaluation import latest_guardrail_results, run_guardrail_evaluation
from app.services.guardrails import GuardrailService
from app.services.orchestrator import LLMServiceClient, RAGServiceClient, TechnicalSupportOrchestrator


router = APIRouter(prefix="/evaluation", tags=["LLM evaluation"])


@dataclass
class _RunState:
    status: str = "running"
    detail: str | None = None
    completed_questions: int = 0
    total_questions: int = 24


_runs: dict[str, _RunState] = {}
_guardrail_runs: dict[str, _RunState] = {}


async def _run_in_background(run_id: str, models: list[str], settings: Settings) -> None:
    def on_progress(completed: int, total: int) -> None:
        state = _runs.get(run_id)
        if state is not None:
            state.completed_questions = completed
            state.total_questions = total

    try:
        await run_evaluation(models, settings.rag_service_url, settings.ollama_base_url, on_progress=on_progress)
        _runs[run_id].status = "completed"
    except Exception as error:  # Keep a useful error in the UI while preserving server availability.
        _runs[run_id].status = "failed"
        _runs[run_id].detail = str(error)[:300]


@router.get("/questions")
async def evaluation_questions() -> dict[str, object]:
    """Expose the fixed task set and Exercise 3 metric definitions."""
    questions = load_questions()
    return {"count": len(questions), "questions": questions, "metrics": METRIC_DEFINITIONS}


@router.get("/latest")
async def latest_evaluation() -> dict[str, object]:
    """Return the most recent complete persisted evaluation report."""
    report = latest_results()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No evaluation has been completed yet.")
    return report


@router.post("/run", response_model=EvaluationRunStarted, status_code=status.HTTP_202_ACCEPTED)
async def start_evaluation(
    request: EvaluationRunRequest,
    settings: Settings = Depends(get_settings),
) -> EvaluationRunStarted:
    """Start a non-blocking three-model run against all fixed questions."""
    if len(set(request.models)) != 3 or any(model not in settings.ollama_models for model in request.models):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select three distinct configured local models.")
    try:
        question_count = len(load_questions())
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error
    run_id = str(uuid4())
    _runs[run_id] = _RunState(total_questions=question_count)
    asyncio.create_task(_run_in_background(run_id, request.models, settings))
    return EvaluationRunStarted(run_id=run_id, status="running", question_count=question_count)


@router.get("/status/{run_id}", response_model=EvaluationStatus)
async def evaluation_status(run_id: str) -> EvaluationStatus:
    """Report background-run completion without returning bulky raw answers."""
    state = _runs.get(run_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run was not found.")
    return EvaluationStatus(
        run_id=run_id,
        status=state.status,
        completed_questions=state.completed_questions,
        total_questions=state.total_questions,
        detail=state.detail,
    )


@router.get("/guardrails/latest")
async def latest_guardrail_evaluation() -> dict[str, object]:
    report = latest_guardrail_results()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No guardrail evaluation has been completed yet.")
    return report


@router.post("/guardrails/run", response_model=EvaluationRunStarted, status_code=status.HTTP_202_ACCEPTED)
async def start_guardrail_evaluation(settings: Settings = Depends(get_settings)) -> EvaluationRunStarted:
    run_id = str(uuid4())
    _guardrail_runs[run_id] = _RunState(total_questions=8)
    service = TechnicalSupportOrchestrator(RAGServiceClient(settings), LLMServiceClient(settings), GuardrailService(settings.max_question_length, settings.rag_max_distance, settings.rag_min_context_characters))
    async def run() -> None:
        try:
            report = await run_guardrail_evaluation(service, settings.max_question_length, settings.ollama_model)
            _guardrail_runs[run_id].completed_questions = report["summary"]["total_tests"]
            _guardrail_runs[run_id].status = "completed"
        except Exception as error:
            _guardrail_runs[run_id].status = "failed"
            _guardrail_runs[run_id].detail = str(error)[:300]
    asyncio.create_task(run())
    return EvaluationRunStarted(run_id=run_id, status="running", question_count=8)


@router.get("/guardrails/status/{run_id}", response_model=EvaluationStatus)
async def guardrail_evaluation_status(run_id: str) -> EvaluationStatus:
    state = _guardrail_runs.get(run_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guardrail evaluation run was not found.")
    return EvaluationStatus(run_id=run_id, status=state.status, completed_questions=state.completed_questions, total_questions=state.total_questions, detail=state.detail)
