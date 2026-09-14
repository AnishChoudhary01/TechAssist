const uploadForm = document.querySelector("#upload-form");
const fileInput = document.querySelector("#document-file");
const fileLabel = document.querySelector("#file-label");
const uploadButton = document.querySelector("#upload-button");
const uploadStatus = document.querySelector("#upload-status");
const dropZone = document.querySelector("#drop-zone");
const knowledgeState = document.querySelector("#knowledge-state");
const documentCount = document.querySelector("#document-count");
const indexedDocuments = document.querySelector("#indexed-documents");
let uploadedCount = 0;

function element(tag, text, className = "") { const node = document.createElement(tag); node.textContent = text; if (className) node.className = className; return node; }
function errorDetail(data, fallback) { const detail = data && data.detail; return typeof detail === "string" && detail ? detail : Array.isArray(detail) && detail.length ? detail.map((item) => item.msg || JSON.stringify(item)).join(" ") : fallback; }
async function readJson(response) { const text = await response.text(); if (!text) throw new Error(`Request failed (${response.status}).`); try { return JSON.parse(text); } catch { throw new Error(text.trim() || `Request failed (${response.status}).`); } }
function setUploadStatus(text, className = "") { uploadStatus.textContent = text; uploadStatus.className = `notice ${className ? `notice-${className}` : ""}`; uploadStatus.hidden = !text; }
function addDocument(result) {
  if (!uploadedCount) indexedDocuments.replaceChildren();
  uploadedCount += 1; documentCount.textContent = `(${uploadedCount})`;
  const item = document.createElement("div"); item.className = "document-item";
  const details = document.createElement("div"); details.append(element("strong", result.source), element("small", `${result.chunks_indexed} indexed chunk${result.chunks_indexed === 1 ? "" : "s"}`));
  item.append(element("span", "▣", "file-icon"), details, element("span", "Indexed", "indexed")); indexedDocuments.append(item);
  knowledgeState.textContent = "Ready"; knowledgeState.className = "index-state";
}

fileInput.addEventListener("change", () => { fileLabel.textContent = fileInput.files[0]?.name || "Drag & drop files here"; });
["dragenter", "dragover"].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); dropZone.classList.add("dragover"); }));
["dragleave", "drop"].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); dropZone.classList.remove("dragover"); }));
dropZone.addEventListener("drop", (event) => { if (event.dataTransfer.files.length) { fileInput.files = event.dataTransfer.files; fileLabel.textContent = event.dataTransfer.files[0].name; } });
uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault(); if (!fileInput.files[0]) return; uploadButton.disabled = true; setUploadStatus("Indexing document…");
  try { const response = await fetch("/api/v1/knowledge/documents", { method: "POST", body: new FormData(uploadForm) }); const data = await readJson(response); if (!response.ok) throw new Error(errorDetail(data, "Document upload failed.")); addDocument(data); setUploadStatus(`${data.source} added to the knowledge base.`, "success"); uploadForm.reset(); fileLabel.textContent = "Drag & drop files here"; } catch (error) { setUploadStatus(error.message, "error"); } finally { uploadButton.disabled = false; }
});
