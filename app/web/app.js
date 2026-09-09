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
let uploadedCount = 0;
let knowledgeReady = false;

function element(tag, text, className = "") { const node = document.createElement(tag); node.textContent = text; if (className) node.className = className; return node; }
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
  askGuidance.textContent = `${result.source} is indexed. Ask a question to retrieve relevant context.`;
}

function resetFlow() { flowItems.forEach((item) => { item.classList.remove("active", "complete"); const note = item.querySelector("small"); if (!note.dataset.default) note.dataset.default = note.textContent; note.textContent = note.dataset.default; }); }
function updateFlow(trace, pending = false) {
  const steps = new Map(trace.map((step) => [step.stage, step]));
  flowItems.forEach((item, index) => { const step = steps.get(item.dataset.stage); const note = item.querySelector("small"); item.classList.remove("active", "complete"); if (step) { item.classList.add("complete"); note.textContent = `${step.detail}${step.duration_ms == null ? "" : ` · ${step.duration_ms} ms`}`; } else if (pending && index === 0) { item.classList.add("active"); note.textContent = "Processing..."; } });
}

function renderSources(items) {
  sources.replaceChildren();
  if (!items.length) { contextSummary.textContent = "No source chunks matched this question."; return; }
  contextSummary.textContent = `${items.length} relevant chunk(s) retrieved`;
  items.forEach((source, index) => { const detail = document.createElement("details"); detail.open = index === 0; const meta = [source.category, source.distance != null ? `distance ${source.distance.toFixed(3)}` : ""].filter(Boolean).join(" · "); detail.append(element("summary", `${source.source}${source.page ? ` · page ${source.page}` : ""}`), element("p", meta, "source-meta"), element("p", source.content, "source-content")); sources.append(detail); });
}

function renderLlmInfo(data) {
  const generation = data.processing_trace.find((step) => step.stage === "Ollama / LLM generation");
  const retrieval = data.processing_trace.find((step) => step.stage === "Knowledge base / RAG retrieval");
  const total = data.processing_trace.find((step) => step.stage === "Final response returned");
  llmInfo.replaceChildren();
  [["Model", data.model], ["Generation", generation?.duration_ms != null ? `${generation.duration_ms} ms` : "—"], ["Retrieval", retrieval?.duration_ms != null ? `${retrieval.duration_ms} ms` : "—"], ["Total", total?.duration_ms != null ? `${total.duration_ms} ms` : "—"]].forEach(([label, value]) => { const row = document.createElement("div"); row.append(element("dt", label), element("dd", value)); llmInfo.append(row); });
  responseMeta.replaceChildren(); [data.model, `${data.sources.length} source${data.sources.length === 1 ? "" : "s"}`].forEach((value) => responseMeta.append(element("span", value)));
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

function renderEvaluation(report) {
  evaluationEmpty.hidden = true; evaluationResults.hidden = false;
  evaluationQuestionCount.textContent = `${report.question_count} fixed tasks`;
  evaluationGeneratedAt.textContent = `Completed ${new Date(report.generated_at_utc).toLocaleString()}`;
  const table = document.createElement("table"); table.className = "comparison-table";
  const headings = ["Model", "Accuracy", "Relevance", "Retrieval", "Hallucination ↓", "Tests", "Latency", "Tokens", "CPU", "Memory", "GPU VRAM"];
  const head = document.createElement("thead"); const headRow = document.createElement("tr"); headings.forEach((heading) => headRow.append(element("th", heading))); head.append(headRow); table.append(head);
  const body = document.createElement("tbody");
  report.comparison.forEach((row) => { const tr = document.createElement("tr"); const cells = [row.model, metricCell(row.accuracy_percent), metricCell(row.relevance_percent), metricCell(row.retrieval_quality_percent), metricCell(row.hallucination_rate_percent), metricCell(row.test_pass_rate_percent), metricCell(row.latency_ms, " ms"), `${metricCell(row.prompt_tokens, "")} / ${metricCell(row.completion_tokens, "")}`, metricCell(row.cpu_percent), metricCell(row.memory_mb, " MB"), metricCell(row.gpu_memory_mb, " MB")]; cells.forEach((cell) => tr.append(element("td", cell))); body.append(tr); });
  table.append(body); evaluationComparison.replaceChildren(table);
}

async function loadLatestEvaluation() {
  try { const response = await fetch("/api/v1/evaluation/latest"); if (response.status === 404) return; const report = await response.json(); if (response.ok) renderEvaluation(report); } catch { /* Evaluation remains optional if the API is temporarily unavailable. */ }
}

async function pollEvaluation(runId) {
  const response = await fetch(`/api/v1/evaluation/status/${runId}`); const data = await response.json();
  if (!response.ok || data.status === "failed") { throw new Error(data.detail || "Evaluation run failed."); }
  if (data.status === "completed") { evaluationStatus.textContent = "Evaluation complete."; await loadLatestEvaluation(); return; }
  evaluationStatus.textContent = "Evaluation running: all 24 questions are being tested against each selected model.";
  window.setTimeout(() => pollEvaluation(runId).catch((error) => { evaluationStatus.textContent = error.message; runEvaluationButton.disabled = false; }), 3000);
}

async function loadModelOptions() {
  try {
    const response = await fetch("/api/v1/support/models"); const data = await response.json();
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
  try { const response = await fetch("/api/v1/knowledge/documents", { method: "POST", body: new FormData(uploadForm) }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Document upload failed."); addDocument(data); setUploadStatus(`${data.source} added to the knowledge base.`, "success"); uploadForm.reset(); fileLabel.textContent = "Drag & drop files here"; } catch (error) { setUploadStatus(error.message, "error"); } finally { uploadButton.disabled = false; }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault(); const question = questionInput.value.trim(); if (question.length < 3) return;
  errorMessage.hidden = true; if (!knowledgeReady) askGuidance.textContent = "No document has been uploaded in this session. The answer will use general troubleshooting guidance.";
  resultPanel.classList.add("is-empty"); submitButton.disabled = true; modelSelect.disabled = true; resetFlow(); updateFlow([], true); setRequestStatus("Analyzing", "working"); flowSummary.textContent = "Retrieving context and generating a grounded answer.";
  try {
    const response = await fetch("/api/v1/support/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, model: modelSelect.value }) }); const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "The request could not be completed.");
    answer.textContent = data.answer; renderSources(data.sources); renderLlmInfo(data); updateFlow(data.processing_trace); resultPanel.classList.remove("is-empty"); setRequestStatus("Complete", "complete"); flowSummary.textContent = "Completed stages include backend timing and source provenance."; resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) { setRequestStatus("Unavailable", "failed"); errorMessage.textContent = error.message; errorMessage.hidden = false; flowSummary.textContent = "The request stopped before a response was available."; } finally { submitButton.disabled = false; modelSelect.disabled = false; }
});

loadModelOptions();
loadLatestEvaluation();

runEvaluationButton.addEventListener("click", async () => {
  const models = [...evaluationModels.querySelectorAll("input:checked")].map((input) => input.value);
  if (models.length !== 3) { evaluationStatus.textContent = "Select exactly three models to start a fair comparison."; return; }
  runEvaluationButton.disabled = true; evaluationStatus.textContent = "Starting controlled evaluation…";
  try { const response = await fetch("/api/v1/evaluation/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ models }) }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Unable to start evaluation."); await pollEvaluation(data.run_id); } catch (error) { evaluationStatus.textContent = error.message; runEvaluationButton.disabled = false; }
});
