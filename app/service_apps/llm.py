"""LLM service entry point: Qwen2.5-Coder generation through Ollama."""

from fastapi import FastAPI

from app.api.v1.llm import router as llm_router


def create_llm_app() -> FastAPI:
    app = FastAPI(
        title="TechAssist LLM Service",
        version="0.4.0",
        description="Generates technical-support responses with Qwen2.5-Coder through Ollama.",
    )
    app.include_router(llm_router)

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "service": "llm"}

    return app


app = create_llm_app()
