from fastapi.testclient import TestClient

from app.api.v1.support import get_support_service
from app.main import create_app


def test_health_check() -> None:
    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_guardrails_page_is_available_from_navigation() -> None:
    client = TestClient(create_app())
    response = client.get("/guardrails")

    assert response.status_code == 200
    assert "Run Guardrail Tests" in response.text
    assert 'href="/guardrails"' in client.get("/workspace").text


class StubSupportService:
    def __init__(self) -> None:
        self.model: str | None = None
        self.use_rag: bool | None = None

    async def answer(self, question: str, model: str | None = None, use_rag: bool = True) -> tuple[str, str, list[object], list[object]]:
        assert question == "The service will not start"
        self.model = model
        self.use_rag = use_rag
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
    assert stub.use_rag is True
    assert body["use_rag"] is True
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


def test_latest_evaluation_returns_json_404_before_a_run() -> None:
    response = TestClient(create_app()).get("/api/v1/evaluation/latest")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert "No evaluation" in response.json()["detail"]


def test_evaluation_questions_endpoint_exposes_fixed_set() -> None:
    response = TestClient(create_app()).get("/api/v1/evaluation/questions")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 24
    assert {item["name"] for item in body["metrics"]} >= {
        "Correctness / Accuracy",
        "Relevance",
        "Retrieval Quality",
        "Hallucination Rate",
        "Test-Pass Rate (generated code)",
        "Response Latency",
        "Token Usage",
        "CPU Consumption",
        "Memory Consumption",
        "GPU Memory Consumption",
    }


def test_ask_support_question_can_disable_rag() -> None:
    app = create_app()
    stub = StubSupportService()
    app.dependency_overrides[get_support_service] = lambda: stub

    response = TestClient(app).post(
        "/api/v1/support/ask",
        json={"question": "The service will not start", "model": "qwen2.5:0.5b", "use_rag": False},
    )

    assert response.status_code == 200
    assert stub.use_rag is False
    assert response.json()["use_rag"] is False
    assert response.json()["sources"] == []


def test_ask_support_question_rejects_an_unconfigured_model() -> None:
    response = TestClient(create_app()).post(
        "/api/v1/support/ask",
        json={"question": "The service will not start", "model": "codellama:7b"},
    )

    assert response.status_code == 422
