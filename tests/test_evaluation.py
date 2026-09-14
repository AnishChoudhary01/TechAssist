from app.services.evaluation import (
    METRIC_DEFINITIONS,
    _code_test,
    _hallucination_rate,
    _term_coverage,
    load_questions,
    questions_file,
)


REQUIRED_METRIC_NAMES = {
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


def test_evaluation_set_has_24_fixed_representative_tasks() -> None:
    questions = load_questions()

    assert questions_file().is_file()
    assert len(questions) == 24
    assert {"troubleshooting", "configuration", "FAQ", "RAG", "code-generation"} <= {item["category"] for item in questions}
    assert all(item["question"] and item["expected_terms"] for item in questions)


def test_proxy_metrics_and_constrained_code_test() -> None:
    answer = "Run chkdsk /f /r."
    assert _term_coverage("Use the AC adapter and save your files.", ["AC adapter", "save"]) == 100.0
    assert _hallucination_rate(answer, "The manual says to save files.") > 0
    assert _code_test("```python\ndef is_valid_port(value):\n    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 65535\n```") is True
    assert _code_test("```python\nimport os\ndef is_valid_port(value):\n    return True\n```") is False


def test_exercise_3_defines_how_every_required_metric_is_calculated() -> None:
    names = {item["name"] for item in METRIC_DEFINITIONS}
    groups = {item["group"] for item in METRIC_DEFINITIONS}

    assert REQUIRED_METRIC_NAMES <= names
    assert groups == {"quality", "performance"}
    assert all(len(item["formula"]) > 40 for item in METRIC_DEFINITIONS)
