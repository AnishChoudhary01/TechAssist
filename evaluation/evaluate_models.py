"""Run the same controlled evaluation module used by the TechAssist UI."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.core.config import get_settings
from app.services.evaluation import run_evaluation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare three TechAssist local models on the fixed 24-task set.")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "results" / "latest.json")
    parser.add_argument("--model", action="append", dest="models", help="Model tag; provide exactly three to override configured defaults.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    models = args.models or list(settings.ollama_models)
    if len(models) != 3 or len(set(models)) != 3:
        raise SystemExit("Select exactly three distinct models with --model, or configure exactly three OLLAMA_MODELS entries.")
    if any(model not in settings.ollama_models for model in models):
        raise SystemExit("Every selected model must appear in OLLAMA_MODELS.")
    report = asyncio.run(run_evaluation(models, settings.rag_service_url, settings.ollama_base_url))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
