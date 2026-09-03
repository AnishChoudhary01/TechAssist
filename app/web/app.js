const form = document.querySelector("#question-form");
const questionInput = document.querySelector("#question");
const questionCount = document.querySelector("#question-count");
const submitButton = document.querySelector("#submit-button");
const status = document.querySelector("#request-status");
const errorMessage = document.querySelector("#error-message");
const resultPanel = document.querySelector("#result-panel");
const answer = document.querySelector("#answer");
const sources = document.querySelector("#sources");
const contextSummary = document.querySelector("#context-summary");
const llmInfo = document.querySelector("#llm-info");
const responseMeta = document.querySelector("#response-meta");
const flowSummary = document.querySelector("#flow-summary");
const flowItems = [...document.querySelectorAll("#flow li")];

questionInput.addEventListener("input", () => {
  questionCount.textContent = `${questionInput.value.length} / 4000`;
});

function setStatus(text, state = "") {
  status.textContent = text;
  status.className = `status ${state}`;
}

function resetFlow() {
  flowItems.forEach((item) => {
    item.classList.remove("active", "complete");
    const description = item.querySelector("small");
    description.textContent = description.dataset.default || description.textContent;
    description.dataset.default = description.textContent;
  });
}

function updateFlow(trace, pending = false) {
  const byStage = new Map(trace.map((step) => [step.stage, step]));
  flowItems.forEach((item, index) => {
    const step = byStage.get(item.dataset.stage);
    const description = item.querySelector("small");
    item.classList.remove("active", "complete");
    if (step) {
      item.classList.add("complete");
      const duration = step.duration_ms === null || step.duration_ms === undefined ? "" : ` · ${step.duration_ms} ms`;
      description.textContent = `${step.detail}${duration}`;
    } else if (pending && index === 0) {
      item.classList.add("active");
      description.textContent = "Question accepted; waiting for service results";
    }
  });
}

function element(tag, text, className = "") {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

function renderSources(retrievedSources) {
  sources.replaceChildren();
  if (!retrievedSources.length) {
    sources.append(element("p", "No indexed context matched this question. The answer is based on general troubleshooting guidance.", "muted"));
    contextSummary.textContent = "0 retrieved chunks";
    return;
  }
  const files = new Set(retrievedSources.map((source) => source.source));
  contextSummary.textContent = `${retrievedSources.length} relevant chunk(s) from ${files.size} document(s)`;
  retrievedSources.forEach((source, index) => {
    const details = document.createElement("details");
    details.open = index === 0;
    const summary = element("summary", source.source + (source.page ? ` · page ${source.page}` : ""));
    const meta = element("p", [source.category, source.distance !== null && source.distance !== undefined ? `similarity distance ${source.distance.toFixed(3)}` : ""].filter(Boolean).join(" · "), "source-meta");
    const content = element("p", source.content, "source-content");
    details.append(summary, meta, content);
    sources.append(details);
  });
}

function renderLlmInfo(data) {
  const generation = data.processing_trace.find((step) => step.stage === "Ollama / Code Llama generation");
  const retrieval = data.processing_trace.find((step) => step.stage === "Knowledge base / RAG retrieval");
  const total = data.processing_trace.find((step) => step.stage === "Final response returned");
  llmInfo.replaceChildren();
  [
    ["Model", data.model],
    ["Provider", "Ollama"],
    ["Generation time", generation?.duration_ms !== undefined ? `${generation.duration_ms} ms` : "Not reported"],
    ["RAG retrieval time", retrieval?.duration_ms !== undefined ? `${retrieval.duration_ms} ms` : "Not reported"],
    ["Total request time", total?.duration_ms !== undefined ? `${total.duration_ms} ms` : "Not reported"],
  ].forEach(([label, value]) => {
    const row = document.createElement("div");
    row.append(element("dt", label), element("dd", value));
    llmInfo.append(row);
  });
  responseMeta.replaceChildren();
  [data.model, `${data.sources.length} context chunk${data.sources.length === 1 ? "" : "s"}`].forEach((value) => responseMeta.append(element("span", value)));
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (question.length < 3) return;

  errorMessage.hidden = true;
  resultPanel.hidden = true;
  submitButton.disabled = true;
  resetFlow();
  updateFlow([], true);
  setStatus("Analyzing", "working");
  flowSummary.textContent = "API orchestration is requesting retrieval and generation.";

  try {
    const response = await fetch("/api/v1/support/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "The request could not be completed.");

    answer.textContent = data.answer;
    renderSources(data.sources);
    renderLlmInfo(data);
    updateFlow(data.processing_trace);
    resultPanel.hidden = false;
    setStatus("Complete", "complete");
    flowSummary.textContent = "Each completed stage reports information from the backend processing trace.";
    resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    setStatus("Unavailable", "failed");
    errorMessage.textContent = error.message;
    errorMessage.hidden = false;
    flowSummary.textContent = "The request stopped before a complete response was available.";
  } finally {
    submitButton.disabled = false;
  }
});
