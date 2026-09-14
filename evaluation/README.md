# Controlled model evaluation

This directory evaluates the unchanged Week 3 TechAssist RAG application with
three locally installed models:

- `qwen2.5-coder:0.5b-instruct`
- `qwen2.5:0.5b`
- `smollm2:360m`

`evaluate_models.py` retrieves the fixed 24-question set once through the RAG
service, freezes those chunks into a prompt, and gives that exact prompt to
every model. The production system prompt is unchanged. Only the Ollama model
tag varies.

## Exercise 3 metrics

Quality: correctness/accuracy, relevance, retrieval quality, hallucination
rate, and code test-pass rate.

Performance: response latency, token usage, CPU, memory, and GPU VRAM.

Each formula is defined in `MODEL_COMPARISON.md` and in
`app.services.evaluation.METRIC_DEFINITIONS`. The same definitions are shown
on the Evaluation card in the UI.

## Run

Start Ollama, RAG, and the API, then either click **Run evaluation** in the UI
or run from the repository root:

```bash
python evaluation/evaluate_models.py --output evaluation/results/latest.json
```

The JSON output preserves each question, retrieved context, answer, metric
breakdown, token counts, latency, and resource samples.
