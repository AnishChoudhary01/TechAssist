"""Run a controlled, repeatable local-model evaluation for TechAssist.

The script retrieves RAG context once for every question and reuses the exact
prompt/context pair for every model.  It writes raw answers and transparent
runtime measurements to JSON; qualitative scores are intentionally recorded
separately in MODEL_COMPARISON.md after review against the rubric.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from time import perf_counter
from typing import Any

import httpx

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.services.orchestrator import SYSTEM_PROMPT


ROOT = Path(__file__).resolve().parent
DEFAULT_MODELS = ["qwen2.5-coder:0.5b-instruct", "qwen2.5:0.5b", "smollm2:360m"]
DEFAULT_RAG_URL = "http://127.0.0.1:8001"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
TOP_K = 4
TEMPERATURE = 0.2
SEED = 42
NUM_PREDICT = 256


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare TechAssist local code models fairly.")
    parser.add_argument("--questions", type=Path, default=ROOT / "questions.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "latest.json")
    parser.add_argument("--rag-url", default=DEFAULT_RAG_URL)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--model", action="append", dest="models", help="Model tag; repeat to override defaults.")
    return parser.parse_args()


def format_context(results: list[dict[str, Any]]) -> str:
    if not results:
        return "No relevant indexed context was found. Use general troubleshooting knowledge and state uncertainty."
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


async def retrieve_all(client: httpx.AsyncClient, questions: list[dict[str, str]], rag_url: str) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for item in questions:
        response = await client.post(f"{rag_url.rstrip('/')}/v1/retrieve", json={"query": item["question"], "limit": TOP_K})
        response.raise_for_status()
        retrieved = response.json()["results"]
        context = format_context(retrieved)
        prepared.append({**item, "retrieved_context": retrieved, "prompt": make_prompt(item["question"], context)})
    return prepared


async def generate(client: httpx.AsyncClient, model: str, prompt: str) -> dict[str, Any]:
    started = perf_counter()
    response = await client.post(
        "/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "system": SYSTEM_PROMPT,
            "stream": False,
            "keep_alive": "0",
            "options": {"num_predict": NUM_PREDICT, "temperature": TEMPERATURE, "seed": SEED},
        },
    )
    response.raise_for_status()
    payload = response.json()
    answer = payload["response"].strip()
    return {
        "answer": answer,
        "latency_ms": round((perf_counter() - started) * 1000),
        "word_count": len(answer.split()),
        "reported_model": payload.get("model", model),
        "ollama_total_duration_ms": round(payload.get("total_duration", 0) / 1_000_000),
        "ollama_eval_count": payload.get("eval_count"),
    }


async def run(args: argparse.Namespace) -> dict[str, Any]:
    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    models = args.models or DEFAULT_MODELS
    timeout = httpx.Timeout(600.0)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as rag_client:
        prepared_questions = await retrieve_all(rag_client, questions, args.rag_url)

    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(base_url=args.ollama_url.rstrip("/"), timeout=timeout, trust_env=False) as ollama_client:
        for question in prepared_questions:
            model_answers: dict[str, Any] = {}
            for model in models:
                print(f"Evaluating {model} on {question['id']}...", flush=True)
                model_answers[model] = await generate(ollama_client, model, question["prompt"])
            results.append(
                {
                    "id": question["id"],
                    "question": question["question"],
                    "retrieved_context": question["retrieved_context"],
                    "prompt": question["prompt"],
                    "answers": model_answers,
                }
            )

    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "application": "TechAssist Week 3 RAG technical-support assistant",
        "models": models,
        "evaluation_conditions": {
            "knowledge_base": "Existing ChromaDB collection queried through the unchanged RAG service",
            "retrieval": {"top_k": TOP_K, "retrieved_once_per_question": True, "shared_across_models": True},
            "prompt": "Production SYSTEM_PROMPT and production prompt template from app.services.orchestrator",
            "generation": {"temperature": TEMPERATURE, "seed": SEED, "num_predict": NUM_PREDICT, "stream": False},
            "execution": "One sequential run per model/question on the same local Ollama server",
        },
        "results": results,
    }


def main() -> None:
    args = parse_args()
    report = asyncio.run(run(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
