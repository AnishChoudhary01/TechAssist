from fastapi.testclient import TestClient

from app.api.v1.support import get_support_service
from app.main import create_app


def test_health_check() -> None:
    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


class StubSupportService:
    async def answer(self, question: str) -> tuple[str, str, list[object], list[object]]:
        assert question == "The service will not start"
        return "Check the service logs and its configured port.", "codellama:7b", [], []


def test_ask_support_question() -> None:
    app = create_app()
    app.dependency_overrides[get_support_service] = lambda: StubSupportService()

    response = TestClient(app).post(
        "/api/v1/support/ask",
        json={"question": "The service will not start"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Check the service logs and its configured port."
    assert body["model"] == "codellama:7b"
    assert body["sources"] == []
    assert [step["stage"] for step in body["processing_trace"]] == [
        "User question received",
        "Final response returned",
    ]
