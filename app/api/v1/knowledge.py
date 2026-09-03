"""Knowledge-base ingestion endpoints exposed by the RAG service."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.config import Settings, get_settings
from app.models.knowledge import DirectoryIngestionResult, IngestionResult
from app.rag.chunking import TextChunker
from app.rag.documents import DocumentLoader, UnsupportedDocumentError
from app.rag.service import KnowledgeBaseService
from app.rag.store import ChromaKnowledgeBase
from app.services.llm.ollama import OllamaConnectionError, OllamaEmbeddingClient, OllamaResponseError

router = APIRouter(prefix="/v1/knowledge", tags=["knowledge base"])


def get_knowledge_base_service(settings: Settings = Depends(get_settings)) -> KnowledgeBaseService:
    """Compose the RAG ingestion and persistence workflow."""
    return KnowledgeBaseService(
        loader=DocumentLoader(),
        chunker=TextChunker(settings.chunk_size, settings.chunk_overlap),
        embedding_client=OllamaEmbeddingClient(settings),
        store=ChromaKnowledgeBase(settings.chroma_persist_directory, settings.rag_collection_name),
    )


@router.post("/documents", response_model=IngestionResult, status_code=status.HTTP_201_CREATED)
async def ingest_document(
    file: UploadFile = File(...),
    category: str | None = Form(default=None, max_length=100),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> IngestionResult:
    """Index one uploaded technical manual, guide, FAQ, or error-code document."""
    try:
        return await service.ingest_upload(file.filename or "upload.txt", await file.read(), category)
    except UnsupportedDocumentError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except OllamaConnectionError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Ollama embedding service is unavailable.") from error
    except OllamaResponseError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Ollama returned invalid embeddings.") from error


@router.post("/index-directory", response_model=DirectoryIngestionResult)
async def index_knowledge_base_directory(
    category: str | None = Form(default=None, max_length=100),
    settings: Settings = Depends(get_settings),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> DirectoryIngestionResult:
    """Index all supported documents in the configured knowledge-base directory."""
    try:
        return await service.ingest_directory(settings.knowledge_base_directory, category)
    except OllamaConnectionError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Ollama embedding service is unavailable.") from error
    except OllamaResponseError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Ollama returned invalid embeddings.") from error
