"""Application/API service entry point, including the RAG/LLM orchestrator."""

from app.main import app, create_app

__all__ = ["app", "create_app"]
