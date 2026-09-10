from app.services.evaluation import _code_test, _hallucination_rate, _rag_analysis, _term_coverage, load_questions


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


def test_rag_analysis_links_chunks_to_each_model_response() -> None:
    results = [{
        "id": "battery-low",
        "question": "What should I do when my Acer laptop shows a battery-low warning?",
        "expected_terms": ["AC adapter", "save"],
        "retrieval_terms": ["AC adapter", "save"],
        "retrieved_context": [
            {"source": "manual.pdf", "page": 1, "content": "Connect the AC adapter and save your work."},
            {"source": "manual.pdf", "page": 2, "content": "An unrelated security section."},
        ],
        "answers": {
            "model-a": {"answer": "Connect the AC adapter and save your work.", "metrics": {"accuracy_percent": 100, "relevance_percent": 100, "hallucination_rate_percent": 0}},
            "model-b": {"answer": "Run chkdsk.", "metrics": {"accuracy_percent": 0, "relevance_percent": 0, "hallucination_rate_percent": 100}},
        },
    }]

    analysis = _rag_analysis(results, ["model-a", "model-b"])[0]

    assert analysis["retrieved_context"][0]["classification"] == "relevant"
    assert analysis["retrieved_context"][1]["classification"] == "irrelevant"
    assert analysis["important_information_missed"] == []
    assert analysis["model_reviews"][0]["correct_response_information"] == ["AC adapter", "save"]
    assert analysis["model_reviews"][1]["hallucination_despite_context"] == ["chkdsk"]
