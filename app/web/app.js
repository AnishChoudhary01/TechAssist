const form = document.querySelector("#question-form");
const questionInput = document.querySelector("#question");
const questionCount = document.querySelector("#question-count");
const submitButton = document.querySelector("#submit-button");
const modelSelect = document.querySelector("#model-select");
const requestStatus = document.querySelector("#request-status");
const errorMessage = document.querySelector("#error-message");
const resultPanel = document.querySelector("#answer-card");
const answer = document.querySelector("#answer");
const sources = document.querySelector("#sources");
const contextSummary = document.querySelector("#context-summary");
const llmInfo = document.querySelector("#llm-info");
const responseMeta = document.querySelector("#response-meta");
const flowSummary = document.querySelector("#flow-summary");
const flowItems = [...document.querySelectorAll("#flow li")];
const uploadForm = document.querySelector("#upload-form");
const fileInput = document.querySelector("#document-file");
const fileLabel = document.querySelector("#file-label");
const uploadButton = document.querySelector("#upload-button");
const uploadStatus = document.querySelector("#upload-status");
const dropZone = document.querySelector("#drop-zone");
const knowledgeState = document.querySelector("#knowledge-state");
const askGuidance = document.querySelector("#ask-guidance");
const documentCount = document.querySelector("#document-count");
const indexedDocuments = document.querySelector("#indexed-documents");
const evaluationModels = document.querySelector("#evaluation-models");
const runEvaluationButton = document.querySelector("#run-evaluation");
const evaluationStatus = document.querySelector("#evaluation-status");
const evaluationEmpty = document.querySelector("#evaluation-empty");
const evaluationResults = document.querySelector("#evaluation-results");
const evaluationComparison = document.querySelector("#evaluation-comparison");
const evaluationQuestionCount = document.querySelector("#evaluation-question-count");
const evaluationGeneratedAt = document.querySelector("#evaluation-generated-at");
const ragToggle = document.querySelector("#rag-toggle");
const analysisGuidance = document.querySelector("#analysis-guidance");
const sourcesMode = document.querySelector("#sources-mode");
const sourcesZone = document.querySelector(".sources-zone");
let uploadedCount = 0;
let knowledgeReady = false;

function element(tag, text, className = "") { const node = document.createElement(tag); node.textContent = text; if (className) node.className = className; return node; }
function errorDetail(data, fallback) {
  const detail = data && data.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail.length) return detail.map((item) => item.msg || JSON.stringify(item)).join(" ");
  return fallback;
}
async function readJson(response) {
  const text = await response.text();
  if (!text) throw new Error(`Request failed (${response.status}).`);
  try { return JSON.parse(text); }
  catch { throw new Error(text.trim() || `Request failed (${response.status}).`); }
}
function setRequestStatus(text, className = "") { requestStatus.textContent = text; requestStatus.className = `request-status ${className}`; }
function setUploadStatus(text, className = "") { uploadStatus.textContent = text; uploadStatus.className = `notice ${className ? `notice-${className}` : ""}`; uploadStatus.hidden = !text; }

function addDocument(result) {
  if (!uploadedCount) indexedDocuments.replaceChildren();
  uploadedCount += 1; documentCount.textContent = `(${uploadedCount})`;
  const item = document.createElement("div"); item.className = "document-item";
  const details = document.createElement("div");
  details.append(element("strong", result.source), element("small", `${result.chunks_indexed} indexed chunk${result.chunks_indexed === 1 ? "" : "s"}`));
  item.append(element("span", "▣", "file-icon"), details, element("span", "Indexed", "indexed"));
  indexedDocuments.append(item); knowledgeReady = true; knowledgeState.textContent = "Ready"; knowledgeState.className = "index-state";
  if (ragToggle?.checked) askGuidance.textContent = `${result.source} is indexed. Ask a question to retrieve relevant context.`;
  else syncRagGuidance();
}

function resetFlow() { flowItems.forEach((item) => { item.classList.remove("active", "complete", "skipped"); const note = item.querySelector("small"); if (!note.dataset.default) note.dataset.default = note.textContent; note.textContent = note.dataset.default; }); }
function updateFlow(trace, pending = false) {
  const steps = new Map(trace.map((step) => [step.stage, step]));
  flowItems.forEach((item, index) => {
    const step = steps.get(item.dataset.stage);
    const note = item.querySelector("small");
    item.classList.remove("active", "complete", "skipped");
    if (step) {
      const skipped = /skipped|RAG mode is off/i.test(step.detail || "");
      item.classList.add(skipped ? "skipped" : "complete");
      note.textContent = `${step.detail}${step.duration_ms == null ? "" : ` · ${step.duration_ms} ms`}`;
    } else if (pending && index === 0) {
      item.classList.add("active");
      note.textContent = "Processing...";
    }
  });
}

function renderSources(items, useRag = true) {
  sources.replaceChildren();
  sourcesZone.classList.toggle("direct-llm", !useRag);
  if (!useRag) {
    sourcesMode.textContent = "Direct LLM";
    contextSummary.textContent = "RAG is off. This response was generated directly by the LLM with no document retrieval.";
    sources.append(element("p", "No knowledge-base chunks were retrieved for this answer.", "source-content"));
    return;
  }
  sourcesMode.textContent = "Relevant chunks";
  if (!items.length) { contextSummary.textContent = "No source chunks matched this question."; return; }
  contextSummary.textContent = `${items.length} relevant chunk(s) retrieved`;
  items.forEach((source, index) => { const detail = document.createElement("details"); detail.open = index === 0; const meta = [source.category, source.distance != null ? `distance ${source.distance.toFixed(3)}` : ""].filter(Boolean).join(" · "); detail.append(element("summary", `${source.source}${source.page ? ` · page ${source.page}` : ""}`), element("p", meta, "source-meta"), element("p", source.content, "source-content")); sources.append(detail); });
}

function renderLlmInfo(data) {
  const generation = data.processing_trace.find((step) => step.stage === "Ollama / LLM generation");
  const retrieval = data.processing_trace.find((step) => step.stage === "Knowledge base / RAG retrieval");
  const total = data.processing_trace.find((step) => step.stage === "Final response returned");
  const retrievalSkipped = /skipped|RAG mode is off/i.test(retrieval?.detail || "");
  llmInfo.replaceChildren();
  [["Model", data.model], ["Mode", data.use_rag ? "RAG on" : "Direct LLM"], ["Generation", generation?.duration_ms != null ? `${generation.duration_ms} ms` : "—"], ["Retrieval", retrievalSkipped ? "Skipped" : retrieval?.duration_ms != null ? `${retrieval.duration_ms} ms` : "—"], ["Total", total?.duration_ms != null ? `${total.duration_ms} ms` : "—"]].forEach(([label, value]) => { const row = document.createElement("div"); row.append(element("dt", label), element("dd", value)); llmInfo.append(row); });
  responseMeta.replaceChildren();
  responseMeta.append(element("span", data.use_rag ? "RAG mode" : "Direct LLM"));
  responseMeta.append(element("span", data.model));
  if (data.use_rag) responseMeta.append(element("span", `${data.sources.length} source${data.sources.length === 1 ? "" : "s"}`));
}

function renderEvaluationModels(models, defaultModel) {
  evaluationModels.replaceChildren();
  models.forEach((model, index) => {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox"; input.value = model; input.checked = index < 3;
    label.append(input, document.createTextNode(model === defaultModel ? `${model} (default)` : model));
    evaluationModels.append(label);
  });
}

function metricCell(value, suffix = "%") { return value == null ? "—" : `${Number(value).toFixed(1)}${suffix}`; }

function renderMetricDefinitions(metrics) {
  const host = document.querySelector("#evaluation-metric-definitions");
  if (!host || !Array.isArray(metrics) || !metrics.length) return;
  host.replaceChildren();
  ["quality", "performance"].forEach((group) => {
    const items = metrics.filter((metric) => metric.group === group);
    if (!items.length) return;
    host.append(element("p", group === "quality" ? "Quality" : "Performance"));
    host.lastElementChild.style.fontWeight = "700";
    const list = document.createElement("ul");
    items.forEach((metric) => {
      const item = document.createElement("li");
      item.append(element("strong", `${metric.name} — `), document.createTextNode(metric.formula));
      list.append(item);
    });
    host.append(list);
  });
}

function renderEvaluation(report) {
  evaluationEmpty.hidden = true; evaluationResults.hidden = false;
  evaluationQuestionCount.textContent = `${report.question_count} fixed tasks`;
  evaluationGeneratedAt.textContent = `Completed ${new Date(report.generated_at_utc).toLocaleString()}`;
  if (Array.isArray(report.metrics)) renderMetricDefinitions(report.metrics);
  const table = document.createElement("table"); table.className = "comparison-table";
  const headings = ["Model", "Accuracy", "Relevance", "Retrieval", "Hallucination ↓", "Test-pass", "Latency", "Tokens (prompt/comp)", "CPU", "Memory", "GPU VRAM"];
  const head = document.createElement("thead"); const headRow = document.createElement("tr"); headings.forEach((heading) => headRow.append(element("th", heading))); head.append(headRow); table.append(head);
  const body = document.createElement("tbody");
  report.comparison.forEach((row) => { const tr = document.createElement("tr"); const cells = [row.model, metricCell(row.accuracy_percent), metricCell(row.relevance_percent), metricCell(row.retrieval_quality_percent), metricCell(row.hallucination_rate_percent), metricCell(row.test_pass_rate_percent), metricCell(row.latency_ms, " ms"), `${metricCell(row.prompt_tokens, "")} / ${metricCell(row.completion_tokens, "")}`, metricCell(row.cpu_percent), metricCell(row.memory_mb, " MB"), metricCell(row.gpu_memory_mb, " MB")]; cells.forEach((cell) => tr.append(element("td", cell))); body.append(tr); });
  table.append(body); evaluationComparison.replaceChildren(table);
}

async function loadLatestEvaluation() {
  try { const response = await fetch("/api/v1/evaluation/latest"); if (response.status === 404) return; const report = await readJson(response); if (response.ok) renderEvaluation(report); } catch { /* Evaluation remains optional if the API is temporarily unavailable. */ }
}

async function pollEvaluation(runId) {
  const response = await fetch(`/api/v1/evaluation/status/${runId}`); const data = await readJson(response);
  if (!response.ok || data.status === "failed") { throw new Error(errorDetail(data, "Evaluation run failed.")); }
  if (data.status === "completed") { evaluationStatus.textContent = "Evaluation complete."; await loadLatestEvaluation(); return; }
  evaluationStatus.textContent = `Evaluation running: ${data.completed_questions || 0} / ${data.total_questions || 24} questions compared on all three models.`;
  window.setTimeout(() => pollEvaluation(runId).catch((error) => { evaluationStatus.textContent = error.message; runEvaluationButton.disabled = false; }), 3000);
}

async function loadModelOptions() {
  try {
    const response = await fetch("/api/v1/support/models"); const data = await readJson(response);
    if (!response.ok || !Array.isArray(data.models)) return;
    modelSelect.replaceChildren();
    data.models.forEach((model) => { const option = document.createElement("option"); option.value = model; option.textContent = model.replace(":", " · "); option.selected = model === data.default_model; modelSelect.append(option); });
    renderEvaluationModels(data.models, data.default_model);
  } catch { /* The default compact model remains selectable when the API is unreachable. */ }
}

questionInput.addEventListener("input", () => { questionCount.textContent = `${questionInput.value.length} / 4000`; });
fileInput.addEventListener("change", () => { fileLabel.textContent = fileInput.files[0]?.name || "Drag & drop files here"; });
["dragenter", "dragover"].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); dropZone.classList.add("dragover"); }));
["dragleave", "drop"].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); dropZone.classList.remove("dragover"); }));
dropZone.addEventListener("drop", (event) => { if (event.dataTransfer.files.length) { fileInput.files = event.dataTransfer.files; fileLabel.textContent = event.dataTransfer.files[0].name; } });

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault(); if (!fileInput.files[0]) return; uploadButton.disabled = true; setUploadStatus("Indexing document…");
  try { const response = await fetch("/api/v1/knowledge/documents", { method: "POST", body: new FormData(uploadForm) }); const data = await readJson(response); if (!response.ok) throw new Error(errorDetail(data, "Document upload failed.")); addDocument(data); setUploadStatus(`${data.source} added to the knowledge base.`, "success"); uploadForm.reset(); fileLabel.textContent = "Drag & drop files here"; } catch (error) { setUploadStatus(error.message, "error"); } finally { uploadButton.disabled = false; }
});

function syncRagGuidance() {
  if (!ragToggle) return;
  if (ragToggle.checked) {
    askGuidance.textContent = knowledgeReady
      ? "Use RAG is on. The answer will retrieve relevant chunks, then generate with Ollama."
      : "Use RAG is on. Ask a technical question; retrieved documents will ground the answer when indexed.";
  } else {
    askGuidance.textContent = "Use RAG is off. The selected model will answer directly with no document retrieval.";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault(); const question = questionInput.value.trim(); if (question.length < 3) return;
  const useRag = Boolean(ragToggle?.checked);
  errorMessage.hidden = true;
  if (useRag && !knowledgeReady) askGuidance.textContent = "No document has been uploaded in this session. RAG will still search the existing knowledge base.";
  if (!useRag) askGuidance.textContent = "Use RAG is off. The selected model will answer directly with no document retrieval.";
  resultPanel.classList.add("is-empty"); submitButton.disabled = true; modelSelect.disabled = true; if (ragToggle) ragToggle.disabled = true; resetFlow(); updateFlow([], true); setRequestStatus("Analyzing", "working"); flowSummary.textContent = useRag ? "Retrieving context and generating a grounded answer." : "Generating a direct LLM answer. Retrieval is skipped.";
  try {
    const response = await fetch("/api/v1/support/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, model: modelSelect.value, use_rag: useRag }) }); const data = await readJson(response);
    if (!response.ok) throw new Error(errorDetail(data, "The request could not be completed."));
    answer.textContent = data.answer; renderSources(data.sources, data.use_rag !== false); renderLlmInfo(data); updateFlow(data.processing_trace); resultPanel.classList.remove("is-empty"); setRequestStatus("Complete", "complete");
    analysisGuidance.textContent = data.use_rag ? "Answer with sources, grounded in retrieved documents." : "Answer generated directly by the LLM. Retrieval was not used.";
    flowSummary.textContent = data.use_rag ? "Completed stages include RAG retrieval, context, and Ollama generation." : "Completed stages: question received, then direct Ollama generation.";
    resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) { setRequestStatus("Unavailable", "failed"); errorMessage.textContent = error.message; errorMessage.hidden = false; flowSummary.textContent = "The request stopped before a response was available."; } finally { submitButton.disabled = false; modelSelect.disabled = false; if (ragToggle) ragToggle.disabled = false; }
});

if (ragToggle) ragToggle.addEventListener("change", syncRagGuidance);
syncRagGuidance();

loadModelOptions();
loadLatestEvaluation();
fetch("/api/v1/evaluation/questions")
  .then((response) => readJson(response))
  .then((data) => { if (Array.isArray(data.metrics)) renderMetricDefinitions(data.metrics); })
  .catch(() => { /* Static formulas in the page remain visible if the API is down. */ });

runEvaluationButton.addEventListener("click", async () => {
  const models = [...evaluationModels.querySelectorAll("input:checked")].map((input) => input.value);
  if (models.length !== 3) { evaluationStatus.textContent = "Select exactly three models to start a fair comparison."; return; }
  runEvaluationButton.disabled = true; evaluationStatus.textContent = "Starting controlled evaluation…";
  try { const response = await fetch("/api/v1/evaluation/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ models }) }); const data = await readJson(response); if (!response.ok) throw new Error(errorDetail(data, "Unable to start evaluation.")); await pollEvaluation(data.run_id); } catch (error) { evaluationStatus.textContent = error.message; runEvaluationButton.disabled = false; }
});
