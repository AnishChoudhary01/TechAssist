# TechAssist – AI Technical Support Assistant

TechAssist is a technical-support assistant that uses Code Llama through Ollama.
It ingests technical manuals, troubleshooting guides, FAQs, error-code documents,
and installation/configuration guides, retrieves relevant excerpts with RAG, then
uses them to ground its troubleshooting response.

The public API service also hosts a single browser UI at `http://127.0.0.1:8000/`.
It displays the complete answer flow—question, API orchestration, RAG retrieval,
retrieved chunks/context, Ollama/Code Llama generation, and the final answer—in
one interface.

All five exercises are implemented:

1. FastAPI application with Ollama + Code Llama generation.
2. Document loading, overlap chunking, Ollama embeddings, and persistent ChromaDB.
3. RAG query embedding, vector similarity search, context retrieval, and grounded generation.
4. Separate API/Application, RAG, and LLM services coordinated by an orchestrator.
5. Dockerfiles and Docker Compose for the complete system.

## Architecture

```text
Client -> API/Application :8000 -> orchestrator -> RAG service :8001 -> ChromaDB + Ollama embeddings
                                              -> LLM service :8002 -> Ollama Code Llama
```

The API service is the public entry point. It first retrieves relevant indexed
context from the RAG service, places that context in the troubleshooting prompt,
then calls the LLM service. The RAG and LLM services can scale independently.

## Prerequisites

- Python 3.11 or newer
- [Ollama](https://ollama.com/) running locally
- The Code Llama and embedding models pulled into Ollama

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
ollama pull codellama:7b
ollama pull nomic-embed-text
```

Optional environment variables (shown in `.env.example`):

```powershell
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:OLLAMA_MODEL = "codellama:7b"
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

Open the TechAssist UI at `http://127.0.0.1:8000/`. It is the recommended way to
ask questions and inspect the end-to-end processing trace. The interactive API
documentation remains available at `http://127.0.0.1:8000/docs`, or call:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/support/ask" `
  -ContentType "application/json" `
  -Body '{"question":"My Python application fails with ModuleNotFoundError. How should I troubleshoot it?"}'
```

Example response:

```json
{
  "answer": "...",
  "model": "codellama:7b",
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

The `ollama-init` service downloads `codellama:7b` and `nomic-embed-text` on its
first run. This can take several minutes. Once it completes, index your mounted
documents through `http://127.0.0.1:8001/v1/knowledge/index-directory`, then use
the public API at `http://127.0.0.1:8000/docs`.

To run the stack in the background, use `docker compose up --build -d`. ChromaDB
and Ollama models persist in named Docker volumes.

## Test

```powershell
.\.venv\Scripts\python -m pytest -q
```
