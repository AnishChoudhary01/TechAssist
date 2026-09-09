# Compact local-model comparison

## Models

| Model | Approximate size | Role in comparison |
| --- | ---: | --- |
| `qwen2.5-coder:0.5b-instruct` | 0.5B | Compact code-focused baseline |
| `qwen2.5:0.5b` | 0.5B | Compact general-instruction model |
| `smollm2:360m` | 0.36B | Smallest local general-instruction model |

## Controlled conditions

- **Application:** unchanged TechAssist Week 3 RAG technical-support assistant.
- **Questions:** the fixed 24-question set in `questions.json`.
- **Knowledge base:** the existing ChromaDB collection; the harness retrieves each
  question once and supplies the same frozen result to each model.
- **Prompt:** the production system prompt and prompt template from
  `app.services.orchestrator`.
- **Generation:** temperature `0.2`, seed `42`, maximum `256` generated tokens,
  non-streaming requests, sequential execution on the same local Ollama server.

## Review rubric

Score every answer from 1 (poor) to 5 (excellent) for each criterion. Record
the ratings in the JSON result or an accompanying review table; do not change
the question, context, or prompt to improve an individual model's result.

| Criterion | What a high score means |
| --- | --- |
| Groundedness | Claims are supported by the retrieved chunks; uncertainty is explicit when needed. |
| Technical correctness | Instructions accurately address the question without unsafe or invented steps. |
| Helpfulness | Advice is clear, actionable, and appropriately ordered. |
| Instruction following | Stays within 250 words and follows the system safety guidance. |
| Efficiency | Lower recorded wall-clock latency with a useful answer. |

Run `evaluation/evaluate_models.py` to generate the raw, auditable result file.

## Run results — 2026-09-09

Raw prompts, retrieved chunks, responses, and timings are saved in
`results/model_comparison_2026-09-09.json`. The figures below summarize a
historical four-question pilot run; it is retained as a baseline. Use the
in-app Evaluation page or `evaluate_models.py` to produce the current 24-task
report at `results/latest.json`.

| Model | Mean latency | Mean answer length | Groundedness | Technical correctness | Helpfulness | Instruction following | Overall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `qwen2.5-coder:0.5b-instruct` | 26.5 s | 190 words | 2.8 | 2.8 | 3.2 | 2.5 | 2.8 |
| `qwen2.5:0.5b` | **23.1 s** | 175 words | **3.0** | **2.8** | 2.8 | **3.0** | **2.9** |
| `smollm2:360m` | 31.4 s | 161 words | 2.0 | 2.0 | 2.2 | 2.2 | 2.1 |

Scores are reviewer ratings on the 1–5 rubric above, averaged across the four
answers; they are qualitative, not model-reported metrics.

### Outcome

`qwen2.5:0.5b` is the best default for this compact-model run: it was the
fastest and was notably accurate for the BIOS-password and Wi-Fi questions.
`qwen2.5-coder:0.5b-instruct` was a close second and produced clearer
step-by-step answers, but it introduced unsupported recovery commands in the
Windows-recovery task. `smollm2:360m` was slowest and leaked the prompt instead
of answering one BIOS question, so it remains available for experimentation but
is not recommended as the default.

All three models hallucinated or added unsupported recovery guidance when the
retrieved context was incomplete. This is a knowledge-base/prompt-safety issue
to address before deployment, not a reason to vary the comparison conditions.
