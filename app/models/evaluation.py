"""Request and status models for the in-app LLM evaluation workflow."""

from pydantic import BaseModel, Field


class EvaluationRunRequest(BaseModel):
    """Exactly three configured models compared on the same fixed task set."""

    models: list[str] = Field(min_length=3, max_length=3)


class EvaluationRunStarted(BaseModel):
    run_id: str
    status: str
    question_count: int


class EvaluationStatus(BaseModel):
    run_id: str
    status: str
    completed_questions: int = 0
    total_questions: int = 24
    detail: str | None = None
