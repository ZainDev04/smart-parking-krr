// Runs the project's Python reasoning engine in the browser for the scenario clock.
// Pyodide (CPython compiled to WebAssembly) loads once; engine.zip is the krr
// package, built by tools/build_site.py. A worker keeps the 3D scene smooth
// while the engine reasons.
const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.29.3/full/";
importScripts(PYODIDE + "pyodide.js");

const ready = (async () => {
  const py = await loadPyodide({ indexURL: PYODIDE });
  const zip = await fetch("engine.zip");
  if (!zip.ok) throw new Error(`engine.zip: HTTP ${zip.status}`);
  py.unpackArchive(await zip.arrayBuffer(), "zip", { extractDir: "/engine" });
  py.runPython("import sys, json\nsys.path.insert(0, '/engine')\nfrom krr.site_export import morning_rush_at");
  return py;
})();

onmessage = async (e) => {
  const { id, date, hour, extra } = e.data;
  try {
    const py = await ready;
    py.globals.set("extra_json", JSON.stringify(extra || []));
    const out = py.runPython(`json.dumps(morning_rush_at(${Number(date)}, ${Number(hour)}, json.loads(extra_json)))`);
    postMessage({ id, ok: true, data: JSON.parse(out) });
  } catch (err) {
    // Python errors end with "ValueError: <message>"; pass on just the message
    const text = String(err && err.message || err).trim();
    const m = text.match(/ValueError: (.*)$/);
    postMessage({ id, ok: false, error: m ? m[1] : text });
  }
};
