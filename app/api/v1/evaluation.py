"""Endpoints for controlled, persistent TechAssist model evaluation."""

import asyncio
from dataclasses import dataclass
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.models.evaluation import EvaluationRunRequest, EvaluationRunStarted, EvaluationStatus
from app.services.evaluation import latest_results, load_questions, run_evaluation


router = APIRouter(prefix="/evaluation", tags=["LLM evaluation"])


@dataclass
class _RunState:
    status: str = "running"
    detail: str | None = None


_runs: dict[str, _RunState] = {}


async def _run_in_background(run_id: str, models: list[str], settings: Settings) -> None:
    try:
        await run_evaluation(models, settings.rag_service_url, settings.ollama_base_url)
        _runs[run_id].status = "completed"
    except Exception as error:  # Keep a useful error in the UI while preserving server availability.
        _runs[run_id].status = "failed"
        _runs[run_id].detail = str(error)[:300]


@router.get("/questions")
async def evaluation_questions() -> dict[str, object]:
    """Expose the fixed task set for transparent evaluation conditions."""
    questions = load_questions()
    return {"count": len(questions), "questions": questions}


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
    run_id = str(uuid4())
    _runs[run_id] = _RunState()
    asyncio.create_task(_run_in_background(run_id, request.models, settings))
    return EvaluationRunStarted(run_id=run_id, status="running", question_count=len(load_questions()))


@router.get("/status/{run_id}", response_model=EvaluationStatus)
async def evaluation_status(run_id: str) -> EvaluationStatus:
    """Report background-run completion without returning bulky raw answers."""
    state = _runs.get(run_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run was not found.")
    return EvaluationStatus(run_id=run_id, status=state.status, detail=state.detail)
