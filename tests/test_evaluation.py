from app.services.evaluation import _code_test, _hallucination_rate, _term_coverage, load_questions


def test_evaluation_set_has_24_fixed_representative_tasks() -> None:
    questions = load_questions()

    assert len(questions) == 24
    assert {"troubleshooting", "configuration", "FAQ", "RAG", "code-generation"} <= {item["category"] for item in questions}
    assert all(item["question"] and item["expected_terms"] for item in questions)


def test_proxy_metrics_and_constrained_code_test() -> None:
    answer = "Run chkdsk /f /r."
    assert _term_coverage("Use the AC adapter and save your files.", ["AC adapter", "save"]) == 100.0
    assert _hallucination_rate(answer, "The manual says to save files.") > 0
    assert _code_test("```python\ndef is_valid_port(value):\n    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 65535\n```") is True
    assert _code_test("```python\nimport os\ndef is_valid_port(value):\n    return True\n```") is False
