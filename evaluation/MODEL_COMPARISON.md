# Exercise 3 — Quantitative evaluation

All three local models are scored on the **same** 24-question set, the **same**
frozen RAG context (retrieved once per question, `top_k=4`), the **same**
production system prompt, and the **same** decoding settings
(`temperature=0.2`, `seed=42`, `num_predict=256`). Only the Ollama model tag
changes.

Run the comparison from the Evaluation card in the UI, or:

```bash
python evaluation/evaluate_models.py --output evaluation/results/latest.json
```

The JSON report stores every answer, frozen context, per-question metric, token
count, latency, and resource sample. The in-app table shows the **mean** of
each metric per model.

## Quality metrics

| Metric | How it is calculated |
| --- | --- |
| **Correctness / Accuracy** | For each question, count how many gold `expected_terms` appear in the answer (case-insensitive substring). `accuracy = 100 × matched / \|expected_terms\|`. Report the mean over 24 questions. Lexical proxy, not an LLM judge. |
| **Relevance** | Mean of (a) expected-term coverage of the answer and (b) coverage of the question’s own whitespace-split tokens in the answer. `relevance = (accuracy_proxy + question-token coverage) / 2`. |
| **Retrieval Quality** | Score the **frozen retrieved context**, not the LLM: `100 × (retrieval_terms found in context) / \|retrieval_terms\|`. Identical across models for a given question because context is retrieved once. |
| **Hallucination Rate** | Count unsupported commands (`chkdsk`, `sfc /scannow`, `msconfig`, `diskpart`, `regedit`, `wget`, `curl`) that appear in the answer but **not** in the retrieved context. `rate = min(100, 100 × unsupported / max(1, sentence_count))`. **Lower is better.** |
| **Test-Pass Rate** | Only the `is_valid_port` code-generation task. Parse with `ast`, allow a safe node set, execute, and check `(1→True, 65535→True, 0→False, 65536→False, "80"→False, True→False)`. `rate = 100 × passed / code_tasks`. Other questions are excluded. |

## Performance metrics

| Metric | How it is calculated |
| --- | --- |
| **Response Latency** | Wall-clock milliseconds around the Ollama `/api/generate` call (`time.perf_counter`), then averaged per model. |
| **Token Usage** | `prompt_eval_count` / `eval_count` from the Ollama response. Table shows mean prompt tokens / mean completion tokens. |
| **CPU consumption** | When an Ollama process is visible on the same host: `100 × (Δ user+system CPU seconds) / wall-clock seconds` during generation, then averaged. May be unavailable in Docker because Ollama is a separate container. |
| **Memory consumption** | Primary: Ollama `/api/ps` `size` for the loaded model, in MB. Fallback: `psutil` RSS of local Ollama processes. |
| **GPU memory** | Ollama `/api/ps` `size_vram` in MB. CPU-only hosts report `0`. |

## Models compared

| Model | Approximate size | Role |
| --- | ---: | --- |
| `qwen2.5-coder:0.5b-instruct` | 0.5B | Compact code-focused baseline |
| `qwen2.5:0.5b` | 0.5B | Compact general-instruction model |
| `smollm2:360m` | 0.36B | Smallest local general-instruction model |

## Latest scores

Open `evaluation/results/latest.json` after a full 24-question run, or read
the Evaluation card in the running app. A four-question qualitative pilot from
2026-09-09 is kept in `results/model_comparison_2026-09-09.json` as a historical
baseline only; do not treat it as the Exercise 3 result.
