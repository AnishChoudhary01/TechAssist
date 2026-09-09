from fastapi.testclient import TestClient

from app.api.v1.support import get_support_service
from app.main import create_app


def test_health_check() -> None:
    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


class StubSupportService:
    def __init__(self) -> None:
        self.model: str | None = None

    async def answer(self, question: str, model: str | None = None) -> tuple[str, str, list[object], list[object]]:
        assert question == "The service will not start"
        self.model = model
        return "Check the service logs and its configured port.", model or "qwen2.5-coder:0.5b-instruct", [], []


def test_ask_support_question() -> None:
    app = create_app()
    stub = StubSupportService()
    app.dependency_overrides[get_support_service] = lambda: stub

    response = TestClient(app).post(
        "/api/v1/support/ask",
        json={"question": "The service will not start", "model": "qwen2.5:0.5b"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Check the service logs and its configured port."
    assert body["model"] == "qwen2.5:0.5b"
    assert stub.model == "qwen2.5:0.5b"
    assert body["sources"] == []
    assert [step["stage"] for step in body["processing_trace"]] == [
        "User question received",
        "Final response returned",
    ]


def test_model_options_expose_only_compact_configured_models() -> None:
    response = TestClient(create_app()).get("/api/v1/support/models")

    assert response.status_code == 200
    assert response.json()["default_model"] == "qwen2.5-coder:0.5b-instruct"
    assert response.json()["models"] == [
        "qwen2.5-coder:0.5b-instruct",
        "qwen2.5:0.5b",
        "smollm2:360m",
    ]


def test_ask_support_question_rejects_an_unconfigured_model() -> None:
    response = TestClient(create_app()).post(
        "/api/v1/support/ask",
        json={"question": "The service will not start", "model": "codellama:7b"},
    )

    assert response.status_code == 422
