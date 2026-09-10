# TechAssist – AI Technical Support Assistant

TechAssist is a technical-support assistant that uses the fast, lightweight
`qwen2.5-coder:0.5b-instruct` model through Ollama by default. Its UI can also
switch between configured compact local models.
It ingests technical manuals, troubleshooting guides, FAQs, error-code documents,
and installation/configuration guides, retrieves relevant excerpts with RAG, then
uses them to ground its troubleshooting response.

The public API service also hosts a single browser UI at `http://127.0.0.1:8000/`.
It displays the complete answer flow—question, API orchestration, RAG retrieval,
retrieved chunks/context, Ollama/LLM generation, and the final answer—in
one interface.

All five exercises are implemented:

1. FastAPI application with Ollama + a lightweight local LLM generation.
2. Document loading, overlap chunking, Ollama embeddings, and persistent ChromaDB.
3. RAG query embedding, vector similarity search, context retrieval, and grounded generation.
4. Separate API/Application, RAG, and LLM services coordinated by an orchestrator.
5. Dockerfiles and Docker Compose for the complete system.

## Architecture

```text
Client -> API/Application :8000 -> orchestrator -> RAG service :8001 -> ChromaDB + Ollama embeddings
                                              -> LLM service :8002 -> Ollama Qwen2.5-Coder 0.5B
```

The API service is the public entry point. It first retrieves relevant indexed
context from the RAG service, places that context in the troubleshooting prompt,
then calls the LLM service. The RAG and LLM services can scale independently.

## Prerequisites

- Python 3.11 or newer
- [Ollama](https://ollama.com/) running locally
- The Qwen2.5-Coder 0.5B and embedding models pulled into Ollama

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
ollama pull qwen2.5-coder:0.5b-instruct
ollama pull qwen2.5:0.5b
ollama pull smollm2:360m
ollama pull nomic-embed-text
```

Optional environment variables (shown in `.env.example`):

```powershell
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:OLLAMA_MODEL = "qwen2.5-coder:0.5b-instruct"
$env:OLLAMA_MODELS = "qwen2.5-coder:0.5b-instruct,qwen2.5:0.5b,smollm2:360m"
$env:OLLAMA_TIMEOUT_SECONDS = "300"
$env:OLLAMA_NUM_PREDICT = "256"
$env:OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"
```

## Run locally (three services)

Start Ollama if it is not already running. Then run each service in a separate terminal:

```powershell
ollama serve
uvicorn app.service_apps.rag:app --reload --port 8001
uvicorn app.service_apps.llm:app --reload --port 8002
uvicorn app.service_apps.api:app --reload --port 8000
```

On some installations Ollama already runs in the background; in that case, do
not start a second `ollama serve` process.

## Build the knowledge base

Put supported `.txt`, `.md`, and text-based `.pdf` documents in
`data/knowledge_base/`, then index the directory:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8001/v1/knowledge/index-directory"
```

Or upload one document directly (the `category` is optional):

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8001/v1/knowledge/documents" `
  -Form @{ file = Get-Item ".\my-troubleshooting-guide.pdf"; category = "troubleshooting guide" }
```

ChromaDB persists vectors in `chroma_data/`. Re-indexing an unchanged chunk
updates it rather than inserting an additional copy.

## Use the public API

Open the TechAssist UI at `http://127.0.0.1:8000/`. Use its Knowledge base panel
to upload a `.txt`, `.md`, or text-based `.pdf` directly; it is chunked, embedded,
and added to ChromaDB immediately. The same UI lets you ask questions and inspect
the end-to-end processing trace. The interactive API documentation remains
available at `http://127.0.0.1:8000/docs`, or call:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/support/ask" `
  -ContentType "application/json" `
  -Body '{"question":"My Python application fails with ModuleNotFoundError. How should I troubleshoot it?"}'
```

Example response:

```json
{
  "answer": "...",
  "model": "qwen2.5-coder:0.5b-instruct",
  "sources": [
    {"content": "...", "source": "guide.pdf", "page": 4}
  ]
}
```

`GET /health` is available on each service. The public API returns `503` when a
required RAG, LLM, or Ollama dependency is not available.

## Run with Docker

Docker Desktop is required. Place documents in `data/knowledge_base/` first, then:

```powershell
docker compose up --build
```

The `ollama-init` service downloads the configured compact models and `nomic-embed-text` on its
first run. This can take several minutes. Once it completes, index your mounted
documents through `http://127.0.0.1:8001/v1/knowledge/index-directory`, then use
the public API at `http://127.0.0.1:8000/docs`.

To run the stack in the background, use `docker compose up --build -d`. ChromaDB
and Ollama models persist in named Docker volumes.

## Test

```powershell
.\.venv\Scripts\python -m pytest -q
```

## Evaluate compact local models

The Evaluation section in the UI runs a fixed set of 24 technical-support,
configuration, FAQ, RAG, and code-generation tasks against exactly three
configured models. Every model receives the same questions, one shared RAG
retrieval per question, the production prompt, and the same generation settings.
It persists raw answers and a comparison with correctness/relevance proxies,
retrieval quality, hallucination proxy rate, code test-pass rate, latency, token
usage, CPU, memory, and Ollama-reported VRAM. The same Evaluation page also
includes a **RAG Analysis** dashboard for selected questions: it presents
question → retrieved chunks → each model response, labels relevant and
irrelevant chunks, lists important expected information missed by retrieval, and
flags tracked hallucinations despite the supplied context.

Open `http://127.0.0.1:8000/`, choose **Evaluation** in the sidebar, and select
**Run evaluation**. The non-blocking run may take several minutes on CPU-only
hardware. Alternatively, start Ollama and the RAG service, then run:

```powershell
.\.venv\Scripts\python .\evaluation\evaluate_models.py `
  --output .\evaluation\results\model_comparison.json
```

Results are saved to `evaluation/results/latest.json`. See
`evaluation/MODEL_COMPARISON.md` for the scoring rubric and controlled
conditions. The quality metrics are transparent deterministic proxies, not an
LLM-as-a-judge score; the raw report retains every answer and retrieved chunk for
review.
