"""Real guardrail and output-test runner, persisted for the evaluation dashboard."""
from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any

from app.services.orchestrator import TechnicalSupportOrchestrator

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evaluation" / "guardrail_questions.json"
RESULTS = ROOT / "evaluation" / "results" / "guardrail_latest.json"


def load_guardrail_questions(max_length: int) -> list[dict[str, Any]]:
    cases = json.loads(DATASET.read_text(encoding="utf-8"))
    for case in cases:
        if case.pop("repeat_to_exceed_max", False):
            case["question"] = case["question"] * (max_length // len(case["question"]) + 2)
    return cases


def _output_checks(case: dict[str, Any], answer: str, sources: list[Any], llm_called: bool) -> dict[str, bool]:
    context = " ".join(source.content.lower() for source in sources)
    words = [word for word in re.findall(r"[a-z]{5,}", answer.lower()) if word not in {"information", "knowledge", "reliably", "enough"}]
    expected_answerable = case["expected_answerable"]
    refusal = (not expected_answerable and not llm_called and any(marker in answer.lower() for marker in ("don't have enough", "do not", "cannot", "can't", "not enough"))) or expected_answerable
    return {
        "relevance": (not llm_called) or any(token in answer.lower() for token in re.findall(r"[a-z]{5,}", case["question"].lower())),
        "grounding": (not llm_called) or bool(context) and all(word in context or word in {"check", "please", "steps", "should", "could", "would"} for word in words[:12]),
        "unsupported_claims": (not llm_called) or not any(command in answer.lower() and command not in context for command in ("chkdsk", "diskpart", "regedit", "wget", "curl")),
        "answerability": (not expected_answerable) or (llm_called and len(answer.strip()) > 20),
        "refusal_behaviour": refusal,
        "response_format": bool(answer.strip()),
    }


async def run_guardrail_evaluation(service: TechnicalSupportOrchestrator, max_length: int, model: str | None = None) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in load_guardrail_questions(max_length):
        answer, used_model, sources, _, decision, llm_called = await service.answer_with_metadata(case["question"], model, True)
        expected = case["expected_behavior"]
        expected_category = {"allow": "ALLOWED", "reject_out_of_scope": "OUT_OF_SCOPE", "reject_insufficient_knowledge": "INSUFFICIENT_KNOWLEDGE", "reject_empty": "EMPTY_OR_MEANINGLESS", "reject_too_long": "INPUT_TOO_LONG"}[expected]
        checks = _output_checks(case, answer, sources, llm_called)
        guardrail_passed = decision.category == expected_category
        # The baseline is deliberately the same real service with admission checks disabled.
        baseline_reaches_llm = False
        try:
            _, _, _, _, _, baseline_reaches_llm = await service.answer_with_metadata(case["question"], model, True, guardrails_enabled=False)
        except Exception as error:
            baseline_reaches_llm = False
        results.append({**case, "actual_behavior": decision.category, "guardrail_result": decision.category, "llm_called": llm_called, "without_guardrail_llm_called": baseline_reaches_llm, "model": used_model, "actual_response": answer, "retrieved_context": [{"source": s.source, "content": s.content, "distance": s.distance} for s in sources], "checks": checks, "guardrail_passed": guardrail_passed, "overall_passed": guardrail_passed and all(checks.values())})
    total = len(results)
    negatives = [r for r in results if not r["expected_answerable"]]
    positives = [r for r in results if r["expected_answerable"]]
    summary = {
        "total_tests": total, "passed": sum(r["overall_passed"] for r in results), "failed": sum(not r["overall_passed"] for r in results),
        "pass_rate": round(100 * sum(r["overall_passed"] for r in results) / total, 1),
        "guardrail_accuracy": round(100 * sum(r["guardrail_passed"] for r in results) / total, 1),
        "false_acceptance": sum(not r["expected_answerable"] and r["llm_called"] for r in negatives),
        "false_rejection": sum(r["expected_answerable"] and not r["llm_called"] for r in positives),
        "correct_rejection_rate": round(100 * sum(not r["llm_called"] for r in negatives) / len(negatives), 1),
        "relevance_pass_rate": round(100 * sum(r["checks"]["relevance"] for r in results) / total, 1),
        "grounding_pass_rate": round(100 * sum(r["checks"]["grounding"] for r in results) / total, 1),
        "refusal_accuracy": round(100 * sum(r["checks"]["refusal_behaviour"] for r in negatives) / len(negatives), 1),
        "unsupported_claim_rate": round(100 * sum(not r["checks"]["unsupported_claims"] for r in results) / total, 1),
    }
    report = {"generated_at_utc": datetime.now(UTC).isoformat(), "summary": summary, "results": results}
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def latest_guardrail_results() -> dict[str, Any] | None:
    return json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else None
