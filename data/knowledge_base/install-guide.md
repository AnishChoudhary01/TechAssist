# TechAssist installation and configuration guide

## Local services

TechAssist is three FastAPI services plus Ollama:

- API / UI: port 8000
- RAG / knowledge base: port 8001 by default (use 8011 if 8001 is already taken)
- LLM generation: port 8002
- Ollama: port 11434

Start Ollama first. Then start RAG, LLM, and API.

Default model: `qwen2.5-coder:1.5b`. Default embedding model may be `nomic-embed-text` or `all-minilm`.

## Indexing documents

Place `.txt`, `.md`, or text PDFs in `data/knowledge_base/`, then:

`POST /v1/knowledge/index-directory` on the RAG service.

Re-indexing an unchanged chunk updates it instead of duplicating it. Vectors persist in `chroma_data/`.

## Configuration file checks

If the API returns HTTP 503:

1. Confirm Ollama is reachable at `http://127.0.0.1:11434`
2. Confirm the RAG service health endpoint returns `{"status":"ok","service":"rag"}`
3. Confirm the LLM service health endpoint returns `{"status":"ok","service":"llm"}`
4. Check `RAG_SERVICE_URL` and `LLM_SERVICE_URL` if the ports were changed
