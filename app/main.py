"""FastAPI application entry point and browser UI host."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.support import router as support_router
from app.api.v1.uploads import router as uploads_router
from app.api.v1.evaluation import router as evaluation_router


def create_app() -> FastAPI:
    """Create and configure the TechAssist API application."""
    app = FastAPI(
        title="TechAssist – AI Technical Support Assistant",
        version="1.0.0",
        description="A transparent technical-support assistant with RAG, Ollama, and a lightweight local LLM.",
    )

    app.include_router(support_router, prefix="/api/v1")
    app.include_router(uploads_router, prefix="/api/v1")
    app.include_router(evaluation_router, prefix="/api/v1")
    web_directory = Path(__file__).parent / "web"
    app.mount("/static", StaticFiles(directory=web_directory), name="static")

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        """Keep unexpected failures as JSON so Safari does not choke on text/plain 500s."""
        if isinstance(exc, StarletteHTTPException):
            return await http_exception_handler(request, exc)
        if isinstance(exc, RequestValidationError):
            return await request_validation_exception_handler(request, exc)
        return JSONResponse(status_code=500, content={"detail": str(exc)[:400] or "Internal Server Error"})

    @app.get("/", include_in_schema=False)
    async def application_ui() -> RedirectResponse:
        """Send the browser UI entry point to the workspace."""
        return RedirectResponse(url="/workspace", status_code=307)

    @app.get("/documents", include_in_schema=False)
    async def documents_ui() -> FileResponse:
        """Serve the document ingestion workspace."""
        return FileResponse(web_directory / "documents.html")

    @app.get("/workspace", include_in_schema=False)
    async def workspace_ui() -> FileResponse:
        """Serve the technical-support analysis workspace."""
        return FileResponse(web_directory / "workspace.html")

    @app.get("/evaluation", include_in_schema=False)
    async def evaluation_ui() -> FileResponse:
        """Serve the model evaluation workspace."""
        return FileResponse(web_directory / "evaluation.html")

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        """Return service liveness without making an upstream LLM request."""
        return {"status": "ok"}

    return app


app = create_app()
