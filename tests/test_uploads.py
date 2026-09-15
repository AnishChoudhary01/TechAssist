from fastapi.testclient import TestClient

from app.api.v1.uploads import get_rag_client
from app.main import create_app
from app.models.knowledge import DocumentListResponse, IndexedDocument, IngestionResult


class StubRAGClient:
    async def upload_document(
        self,
        filename: str,
        content: bytes,
        content_type: str | None,
        category: str | None,
    ) -> IngestionResult:
        assert filename == "guide.txt"
        assert content == b"Restart the service after changing its configuration."
        assert content_type == "text/plain"
        assert category == "installation guide"
        return IngestionResult(source=filename, chunks_indexed=1)

    async def list_documents(self) -> DocumentListResponse:
        return DocumentListResponse(documents=[
            IndexedDocument(
                document_id="document-1",
                filename="guide.txt",
                status="indexed",
                chunks_indexed=1,
                category="installation guide",
                indexed_at="2026-09-14T00:00:00+00:00",
            )
        ])


def test_upload_document_to_knowledge_base() -> None:
    app = create_app()
    app.dependency_overrides[get_rag_client] = lambda: StubRAGClient()

    response = TestClient(app).post(
        "/api/v1/knowledge/documents",
        data={"category": "installation guide"},
        files={"file": ("guide.txt", b"Restart the service after changing its configuration.", "text/plain")},
    )

    assert response.status_code == 201
    assert response.json() == {"source": "guide.txt", "chunks_indexed": 1}


def test_document_list_uses_rag_service_records() -> None:
    app = create_app()
    app.dependency_overrides[get_rag_client] = lambda: StubRAGClient()

    response = TestClient(app).get("/api/v1/knowledge/documents")

    assert response.status_code == 200
    assert response.json()["documents"] == [{
        "document_id": "document-1",
        "filename": "guide.txt",
        "status": "indexed",
        "chunks_indexed": 1,
        "category": "installation guide",
        "indexed_at": "2026-09-14T00:00:00+00:00",
    }]
