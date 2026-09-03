"""RAG service entry point: ingestion, embedding, ChromaDB, and retrieval."""

from fastapi import FastAPI

from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.rag import router as rag_router


def create_rag_app() -> FastAPI:
    app = FastAPI(
        title="TechAssist RAG Service",
        version="0.4.0",
        description="Indexes technical documentation and retrieves relevant support context.",
    )
    app.include_router(knowledge_router)
    app.include_router(rag_router)

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "service": "rag"}

    return app


app = create_rag_app()
