# Common application error codes

## HTTP 503 Service Unavailable

In TechAssist this means a required upstream service failed. The public API returns 503 when RAG, LLM, or Ollama cannot complete a request.

Fix by starting the missing service, then retry. Do not treat 503 as an application logic bug until health checks pass.

## HTTP 502 Bad Gateway

Ollama returned a body the LLM or RAG service could not parse, or the model produced an empty response. Confirm the model name with `ollama list` and that `OLLAMA_MODEL` matches an installed tag.

## Port already in use

If uvicorn cannot bind 8001, another project is using that port. Run the RAG service on 8011 and set `RAG_SERVICE_URL=http://127.0.0.1:8011` for the API process.

## Empty retrieval results

If RAG returns no chunks, the knowledge base has not been indexed, or the query does not match indexed text. Run `POST /v1/knowledge/index-directory` after adding documents.
