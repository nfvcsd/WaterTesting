// Page logic: pick a datalog, hand it to the converter worker, download the result.
// The heavy lifting (Python via Pyodide) happens in worker.js so the page stays responsive.

const MAX_FILE_BYTES = 50 * 1024 * 1024;
const XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

const form = document.getElementById("report-form");
const fileInput = document.getElementById("datalog");
const dropzone = document.getElementById("dropzone");
const fileNameLabel = document.getElementById("file-name");
const minChlorineInput = document.getElementById("min-chlorine");
const convertButton = document.getElementById("convert");
const statusLine = document.getElementById("status");
const resultPanel = document.getElementById("result");
const resultSummary = document.getElementById("result-summary");
const resultWarning = document.getElementById("result-warning");
const downloadAgain = document.getElementById("download-again");

const worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });

let converterReady = false;
let busy = false;
let selectedFile = null;
let reportUrl = null;

worker.addEventListener("message", ({ data }) => {
  if (data.type === "ready") {
    converterReady = true;
    setStatus(selectedFile ? "" : "Ready. Choose a datalog to begin.");
    refreshButton();
  } else if (data.type === "startup-failed") {
    setStatus(
      "The converter couldn't start. Try reloading the page, or use a current version of Chrome, Edge, Safari or Firefox.",
      "error",
    );
    console.error(data.error);
  } else if (data.type === "result") {
    busy = false;
    refreshButton();
    if (data.ok) {
      showResult(data);
    } else {
      setStatus(data.error, "error");
    }
  }
});

loadDefaults();
setStatus("Getting the converter ready… The first visit takes a few seconds.", "busy");

fileInput.addEventListener("change", () => chooseFile(fileInput.files[0]));

for (const eventName of ["dragenter", "dragover"]) {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.add("is-dragging");
  });
}
for (const eventName of ["dragleave", "drop"]) {
  dropzone.addEventListener(eventName, () => dropzone.classList.remove("is-dragging"));
}
dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  chooseFile(event.dataTransfer.files[0]);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedFile || !converterReady || busy) return;

  const minChlorine = readMinChlorine();
  if (minChlorine === false) {
    setStatus("Enter the minimum as a number like 0.3, or leave it blank.", "error");
    minChlorineInput.focus();
    return;
  }

  busy = true;
  refreshButton();
  resultPanel.hidden = true;
  setStatus("Making the report…", "busy");

  const xml = await selectedFile.arrayBuffer();
  worker.postMessage({ xml, name: selectedFile.name, minChlorine }, [xml]);
});

function chooseFile(file) {
  resultPanel.hidden = true;
  selectedFile = null;
  dropzone.classList.remove("has-file");
  fileNameLabel.hidden = true;

  if (!file) {
    refreshButton();
    return;
  }
  if (!file.name.toLowerCase().endsWith(".xml")) {
    setStatus(`"${file.name}" isn't an .xml file. Choose the datalog exported from the analyzer.`, "error");
  } else if (file.size > MAX_FILE_BYTES) {
    setStatus(`"${file.name}" is larger than 50 MB, which is too big for a datalog.`, "error");
  } else {
    selectedFile = file;
    dropzone.classList.add("has-file");
    fileNameLabel.textContent = file.name;
    fileNameLabel.hidden = false;
    setStatus(converterReady ? "" : "Getting the converter ready…", converterReady ? "" : "busy");
  }
  refreshButton();
}

/** The minimum as a number, undefined when blank, or false when invalid. */
function readMinChlorine() {
  const text = minChlorineInput.value.trim();
  if (text === "") return undefined;
  const value = Number(text);
  return Number.isFinite(value) && value >= 0 ? value : false;
}

function showResult(result) {
  if (reportUrl) URL.revokeObjectURL(reportUrl);
  reportUrl = URL.createObjectURL(new Blob([result.bytes], { type: XLSX_TYPE }));

  downloadAgain.href = reportUrl;
  downloadAgain.download = result.filename;
  downloadAgain.click();

  const plural = (count, word) => `${count.toLocaleString()} ${word}${count === 1 ? "" : "s"}`;
  resultSummary.textContent =
    `${result.filename} has been downloaded: ${plural(result.days, "day")} from ` +
    `${plural(result.readings, "reading")}.` +
    (result.skipped ? ` ${plural(result.skipped, "entry")} couldn't be read and were skipped.` : "");

  if (result.low_days.length) {
    resultWarning.textContent =
      `Free chlorine dropped below the minimum on ${plural(result.low_days.length, "day")}: ` +
      `${result.low_days.join(", ")}. These days are shaded in the report.`;
    resultWarning.hidden = false;
  } else {
    resultWarning.hidden = true;
  }

  resultPanel.hidden = false;
  setStatus("");
}

async function loadDefaults() {
  try {
    const response = await fetch("config.json");
    const config = await response.json();
    if (typeof config.default_min_chlorine === "number") {
      minChlorineInput.value = config.default_min_chlorine;
    }
  } catch (error) {
    console.warn("No config.json defaults loaded", error);
  }
}

function refreshButton() {
  convertButton.disabled = !(selectedFile && converterReady && !busy);
}

function setStatus(message, kind = "") {
  statusLine.textContent = message;
  statusLine.classList.toggle("is-busy", kind === "busy");
  statusLine.classList.toggle("is-error", kind === "error");
}
