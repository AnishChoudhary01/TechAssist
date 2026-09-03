"""Request and response models for the LLM service."""

from pydantic import BaseModel, Field


class GenerationRequest(BaseModel):
    prompt: str = Field(min_length=1)
    system_prompt: str = Field(min_length=1)


class GenerationResponse(BaseModel):
    answer: str
    model: str
