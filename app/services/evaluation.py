"""Controlled local-model evaluation for the TechAssist RAG application."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
import json
from pathlib import Path
import re
from time import perf_counter
from typing import Any

import httpx

from app.services.orchestrator import SYSTEM_PROMPT

try:  # psutil is optional in constrained Docker/local environments.
    import psutil
except ImportError:  # pragma: no cover - exercised only without optional package
    psutil = None


ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_FILE = ROOT / "evaluation" / "questions.json"
RESULTS_FILE = ROOT / "evaluation" / "results" / "latest.json"
TOP_K = 4
TEMPERATURE = 0.2
SEED = 42
NUM_PREDICT = 256
SUSPICIOUS_COMMANDS = ("chkdsk", "sfc /scannow", "msconfig", "diskpart", "regedit", "wget", "curl")
RAG_ANALYSIS_IDS = ("battery-low", "supervisor-password", "windows-recovery", "wireless-connection", "factory-reset", "rag-source-check")


def load_questions() -> list[dict[str, Any]]:
    """Return the fixed, versioned evaluation set used by every model."""
    return json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))


def format_context(results: list[dict[str, Any]]) -> str:
    if not results:
        return "No relevant indexed context was found. State uncertainty and describe safe next checks."
    return "\n\n".join(
        "[Source: {source}{page}]\n{content}".format(
            source=item["source"],
            page=f", page {item['page']}" if item.get("page") else "",
            content=item["content"],
        )
        for item in results
    )


def make_prompt(question: str, context: str) -> str:
    return (
        f"Technical support question:\n{question}\n\n"
        f"Knowledge-base context:\n{context}\n\n"
        "Provide a helpful troubleshooting response in at most 250 words. If the supplied context is insufficient, say what to check next."
    )


def _percent(matches: int, total: int) -> float:
    return round((100 * matches / total) if total else 100.0, 1)


def _term_coverage(text: str, terms: list[str]) -> float:
    lowered = text.lower()
    return _percent(sum(term.lower() in lowered for term in terms), len(terms))


def _hallucination_rate(answer: str, context: str) -> float:
    """Return an auditable conservative proxy, not an LLM-judge claim of fact."""
    unsupported = _unsupported_commands(answer, context)
    sentences = max(1, len(re.findall(r"[.!?]+", answer)))
    return round(min(100, 100 * len(unsupported) / sentences), 1)


def _unsupported_commands(answer: str, context: str) -> list[str]:
    """List tracked commands that were generated without RAG support."""
    lowered_answer, lowered_context = answer.lower(), context.lower()
    return [command for command in SUSPICIOUS_COMMANDS if command in lowered_answer and command not in lowered_context]


def _rag_analysis(results: list[dict[str, Any]], models: list[str]) -> list[dict[str, Any]]:
    """Build reviewable retrieval-to-response records for selected evaluation tasks."""
    analyses: list[dict[str, Any]] = []
    for item in results:
        if item["id"] not in RAG_ANALYSIS_IDS:
            continue
        retrieval_terms = item.get("retrieval_terms", [])
        expected_terms = item["expected_terms"]
        context = format_context(item["retrieved_context"])
        chunks = []
        for chunk in item["retrieved_context"]:
            matched_terms = [term for term in retrieval_terms if term.lower() in chunk["content"].lower()]
            chunks.append({
                "source": chunk["source"], "page": chunk.get("page"), "content": chunk["content"],
                "classification": "relevant" if matched_terms else "irrelevant",
                "relevant_information": matched_terms,
            })
        irrelevant_count = sum(chunk["classification"] == "irrelevant" for chunk in chunks)
        retrieval_quality = _term_coverage(context, retrieval_terms)
        context_quality = round((retrieval_quality + _percent(len(chunks) - irrelevant_count, len(chunks))) / 2, 1)
        model_reviews = []
        for model in models:
            answer = item["answers"][model]
            correct_information = [term for term in expected_terms if term.lower() in answer["answer"].lower()]
            unsupported = _unsupported_commands(answer["answer"], context)
            response_quality = round((answer["metrics"]["accuracy_percent"] + answer["metrics"]["relevance_percent"] + (100 - answer["metrics"]["hallucination_rate_percent"])) / 3, 1)
            model_reviews.append({
                "model": model, "response": answer["answer"], "correct_response_information": correct_information,
                "hallucination_despite_context": unsupported, "response_quality_percent": response_quality,
            })
        analyses.append({
            "id": item["id"], "question": item["question"], "retrieval_quality_percent": retrieval_quality,
            "context_quality_percent": context_quality, "retrieved_context": chunks,
            "important_information_missed": [term for term in expected_terms if term.lower() not in context.lower()],
            "model_reviews": model_reviews,
        })
    return analyses


def _code_test(answer: str) -> bool | None:
    """Safely test the single constrained code-generation task, if code is present."""
    match = re.search(r"```(?:python)?\s*(.*?)```", answer, flags=re.IGNORECASE | re.DOTALL)
    source = match.group(1) if match else answer
    try:
        tree = ast.parse(source.strip())
    except SyntaxError:
        return False
    allowed = {
        ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.IfExp, ast.Compare,
        ast.BoolOp, ast.And, ast.Or, ast.Name, ast.Load, ast.Constant, ast.UnaryOp, ast.USub, ast.Not,
        ast.Is, ast.IsNot, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Call,
    }
    if any(type(node) not in allowed for node in ast.walk(tree)):
        return False
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    if any(not isinstance(call.func, ast.Name) or call.func.id != "isinstance" for call in calls):
        return False
    function = next((node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "is_valid_port"), None)
    if function is None or len(tree.body) != 1:
        return False
    namespace: dict[str, Any] = {"__builtins__": {"isinstance": isinstance, "int": int, "bool": bool}}
    try:
        exec(compile(tree, "<evaluation-answer>", "exec"), namespace, namespace)
        validator = namespace["is_valid_port"]
        return all(
            validator(value) is expected
            for value, expected in ((1, True), (65535, True), (0, False), (65536, False), ("80", False), (True, False))
        )
    except Exception:
        return False


def _resource_snapshot() -> tuple[float | None, int | None]:
    if psutil is None:
        return None, None
    cpu_seconds, memory_bytes = 0.0, 0
    for process in psutil.process_iter(["name", "memory_info", "cpu_times"]):
        try:
            if (process.info["name"] or "").lower().startswith("ollama"):
                cpu = process.info["cpu_times"]
                cpu_seconds += cpu.user + cpu.system
                memory_bytes += process.info["memory_info"].rss
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return cpu_seconds, memory_bytes


async def _gpu_memory_mb(client: httpx.AsyncClient, model: str) -> float | None:
    try:
        models = (await client.get("/api/ps")).json().get("models", [])
        entry = next((item for item in models if item.get("name") == model), None)
        return round(entry.get("size_vram", 0) / (1024 * 1024), 1) if entry else 0.0
    except (httpx.HTTPError, ValueError, TypeError):
        return None


async def _retrieve_all(client: httpx.AsyncClient, questions: list[dict[str, Any]], rag_url: str) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for item in questions:
        response = await client.post(f"{rag_url.rstrip('/')}/v1/retrieve", json={"query": item["question"], "limit": TOP_K})
        response.raise_for_status()
        retrieved = response.json()["results"]
        context = format_context(retrieved)
        prepared.append({**item, "retrieved_context": retrieved, "prompt": make_prompt(item["question"], context)})
    return prepared


async def _generate(client: httpx.AsyncClient, model: str, item: dict[str, Any]) -> dict[str, Any]:
    before_cpu, before_memory = _resource_snapshot()
    started = perf_counter()
    response = await client.post(
        "/api/generate",
        json={
            "model": model, "prompt": item["prompt"], "system": SYSTEM_PROMPT, "stream": False,
            "keep_alive": "2m", "options": {"num_predict": NUM_PREDICT, "temperature": TEMPERATURE, "seed": SEED},
        },
    )
    response.raise_for_status()
    elapsed = perf_counter() - started
    payload = response.json()
    answer = payload["response"].strip()
    after_cpu, after_memory = _resource_snapshot()
    context = format_context(item["retrieved_context"])
    test_passed = _code_test(answer) if item.get("code_test") else None
    return {
        "answer": answer,
        "latency_ms": round(elapsed * 1000),
        "token_usage": {"prompt": payload.get("prompt_eval_count", 0), "completion": payload.get("eval_count", 0)},
        "resource_usage": {
            "cpu_percent": round((after_cpu - before_cpu) / elapsed * 100, 1) if before_cpu is not None and after_cpu is not None else None,
            "memory_mb": round((after_memory or 0) / (1024 * 1024), 1) if after_memory is not None else None,
            "gpu_memory_mb": await _gpu_memory_mb(client, model),
        },
        "metrics": {
            "accuracy_percent": _term_coverage(answer, item["expected_terms"]),
            "relevance_percent": round((_term_coverage(answer, item["expected_terms"]) + _term_coverage(answer, item["question"].split())) / 2, 1),
            "retrieval_quality_percent": _term_coverage(context, item.get("retrieval_terms", [])),
            "hallucination_rate_percent": _hallucination_rate(answer, context),
            "test_passed": test_passed,
        },
    }


def _mean(values: list[float | int | None]) -> float | None:
    actual = [value for value in values if value is not None]
    return round(sum(actual) / len(actual), 1) if actual else None


def _aggregate(results: list[dict[str, Any]], models: list[str]) -> list[dict[str, Any]]:
    comparison: list[dict[str, Any]] = []
    for model in models:
        answers = [result["answers"][model] for result in results]
        code = [answer["metrics"]["test_passed"] for answer in answers if answer["metrics"]["test_passed"] is not None]
        comparison.append({
            "model": model,
            "accuracy_percent": _mean([answer["metrics"]["accuracy_percent"] for answer in answers]),
            "relevance_percent": _mean([answer["metrics"]["relevance_percent"] for answer in answers]),
            "retrieval_quality_percent": _mean([answer["metrics"]["retrieval_quality_percent"] for answer in answers]),
            "hallucination_rate_percent": _mean([answer["metrics"]["hallucination_rate_percent"] for answer in answers]),
            "test_pass_rate_percent": _percent(sum(code), len(code)) if code else None,
            "latency_ms": _mean([answer["latency_ms"] for answer in answers]),
            "prompt_tokens": _mean([answer["token_usage"]["prompt"] for answer in answers]),
            "completion_tokens": _mean([answer["token_usage"]["completion"] for answer in answers]),
            "cpu_percent": _mean([answer["resource_usage"]["cpu_percent"] for answer in answers]),
            "memory_mb": _mean([answer["resource_usage"]["memory_mb"] for answer in answers]),
            "gpu_memory_mb": _mean([answer["resource_usage"]["gpu_memory_mb"] for answer in answers]),
        })
    return comparison


async def run_evaluation(models: list[str], rag_url: str, ollama_url: str) -> dict[str, Any]:
    """Run all fixed questions against every selected model under shared conditions."""
    questions = load_questions()
    timeout = httpx.Timeout(600.0)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as rag_client:
        prepared = await _retrieve_all(rag_client, questions, rag_url)
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(base_url=ollama_url.rstrip("/"), timeout=timeout, trust_env=False) as ollama_client:
        for item in prepared:
            answers = {model: await _generate(ollama_client, model, item) for model in models}
            results.append({key: value for key, value in item.items() if key != "prompt"} | {"answers": answers})
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(), "models": models, "question_count": len(questions),
        "conditions": {"shared_questions": True, "retrieved_once_per_question": True, "top_k": TOP_K, "temperature": TEMPERATURE, "seed": SEED, "num_predict": NUM_PREDICT},
        "metric_notes": {"accuracy_relevance": "Expected-term coverage proxy", "retrieval_quality": "Expected retrieval-term coverage proxy", "hallucination_rate": "Unsupported-command sentence proxy", "resource_usage": "Host Ollama process RSS/CPU delta and Ollama-reported VRAM"},
        "results": results,
    }
    report["comparison"] = _aggregate(results, models)
    report["rag_analysis"] = _rag_analysis(results, models)
    report["rag_analysis_notes"] = {
        "retrieval_quality": "Expected retrieval-term coverage in all retrieved chunks.",
        "context_quality": "Retrieval quality combined with the percentage of chunks classified relevant.",
        "response_quality": "Average of answer accuracy proxy, relevance proxy, and inverse unsupported-command rate.",
        "review_labels": "Relevant/irrelevant chunks and correct response information use fixed expected terms; hallucination flags only tracked unsupported commands.",
    }
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def latest_results() -> dict[str, Any] | None:
    return json.loads(RESULTS_FILE.read_text(encoding="utf-8")) if RESULTS_FILE.exists() else None
