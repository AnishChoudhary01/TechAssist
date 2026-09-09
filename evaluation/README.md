# Controlled model evaluation

This directory evaluates the unchanged Week 3 TechAssist RAG application with
three locally installed code models:

- `qwen2.5-coder:0.5b-instruct`
- `qwen2.5:0.5b`
- `smollm2:360m`

`evaluate_models.py` retrieves the fixed 24-question set once through the existing RAG
service, freezes the returned chunks into a prompt, and gives that exact prompt
to every model. It uses the production system prompt and answer template. The
only thing that varies is the selected LLM model tag.

## Run

Start Ollama and the RAG service, then run from the repository root:

```powershell
.\.venv\Scripts\python .\evaluation\evaluate_models.py `
  --output .\evaluation\results\model_comparison.json
```

The JSON output preserves each question, retrieved context, complete prompt,
answer, correctness/relevance/retrieval and hallucination proxy metrics, code
test result where applicable, token counts, latency, and resource samples. This
makes a future evaluation auditable and repeatable. Do not substitute
model-specific prompts or contexts.
