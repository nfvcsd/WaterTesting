// Runs the water_report Python package in the browser with Pyodide.
//
// Pyodide and the Python wheels are served from this same site (see
// scripts/build_site.py), so nothing is fetched from a third party and the
// datalog never leaves the user's computer.

import { loadPyodide } from "./pyodide/pyodide.mjs";

const INPUT_PATH = "/tmp/datalog.xml";
const OUTPUT_PATH = "/tmp/report.xlsx";

const converter = startConverter();

converter.then(
  () => postMessage({ type: "ready" }),
  (error) => postMessage({ type: "startup-failed", error: String(error) }),
);

async function startConverter() {
  const pyodide = await loadPyodide({ indexURL: new URL("./pyodide/", import.meta.url).href });

  const wheels = await fetchOk("./wheels/manifest.json").then((response) => response.json());
  for (const wheel of wheels) {
    const response = await fetchOk(`./wheels/${wheel}`);
    pyodide.unpackArchive(await response.arrayBuffer(), "wheel");
  }

  return { pyodide, convert: pyodide.pyimport("water_report.web").convert };
}

self.addEventListener("message", async ({ data }) => {
  const { xml, name, minChlorine } = data;
  try {
    const { pyodide, convert } = await converter;
    pyodide.FS.writeFile(INPUT_PATH, new Uint8Array(xml));

    // undefined (not null) becomes Python's None.
    const result = JSON.parse(convert(INPUT_PATH, name, OUTPUT_PATH, minChlorine ?? undefined));
    if (!result.ok) {
      postMessage({ type: "result", ...result });
      return;
    }

    const bytes = pyodide.FS.readFile(OUTPUT_PATH);
    postMessage({ type: "result", ...result, bytes }, [bytes.buffer]);
  } catch (error) {
    console.error(error);
    postMessage({
      type: "result",
      ok: false,
      error: "Something went wrong making the report. Please send the datalog to the Technology Department.",
    });
  } finally {
    const { pyodide } = await converter.catch(() => ({}));
    for (const path of [INPUT_PATH, OUTPUT_PATH]) {
      try {
        pyodide?.FS.unlink(path);
      } catch {
        // File was never written.
      }
    }
  }
});

async function fetchOk(path) {
  const response = await fetch(new URL(path, import.meta.url));
  if (!response.ok) {
    throw new Error(`Could not load ${path} (${response.status})`);
  }
  return response;
}
