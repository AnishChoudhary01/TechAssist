"""Public knowledge-base upload endpoint used by the TechAssist browser UI."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.config import Settings, get_settings
from app.models.knowledge import IngestionResult
from app.services.orchestrator import RAGServiceClient, UpstreamServiceError

router = APIRouter(prefix="/knowledge", tags=["knowledge base"])


def get_rag_client(settings: Settings = Depends(get_settings)) -> RAGServiceClient:
    """Provide the public API's client for the private RAG service."""
    return RAGServiceClient(settings)


@router.post("/documents", response_model=IngestionResult, status_code=status.HTTP_201_CREATED)
async def upload_knowledge_document(
    file: UploadFile = File(...),
    category: str | None = Form(default=None, max_length=100),
    rag_client: RAGServiceClient = Depends(get_rag_client),
) -> IngestionResult:
    """Upload a supported document and add its chunks to the knowledge base."""
    try:
        return await rag_client.upload_document(
            filename=file.filename or "upload.txt",
            content=await file.read(),
            content_type=file.content_type,
            category=category,
        )
    except UpstreamServiceError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"{error.service} failed: {error.detail}") from error
