const API = "";  // same origin

let activeRunId = null;
let activeSSE = null;

// ── Boot ──────────────────────────────────────────────────────────────────────
(async () => {
  await Promise.all([loadStatus(), loadScrapers(), loadRuns()]);
})();

// ── Polling ───────────────────────────────────────────────────────────────────
setInterval(loadStatus, 8000);
setInterval(loadRuns,   15000);

// ── Status ────────────────────────────────────────────────────────────────────
async function loadStatus() {
  try {
    const s = await fetch(`${API}/status`).then(r => r.json());
    document.getElementById("stat-open").textContent  = s.jobs_open  ?? "—";
    document.getElementById("stat-leads").textContent = s.leads      ?? "—";
    document.getElementById("stat-total").textContent = s.jobs_total ?? "—";

    const btn = document.getElementById("run-btn");
    if (s.active_run) {
      btn.disabled = true;
      btn.textContent = "Running…";
    } else {
      btn.disabled = false;
      btn.textContent = "Run now";
    }
  } catch {}
}

// ── Scrapers ──────────────────────────────────────────────────────────────────
async function loadScrapers() {
  try {
    const scrapers = await fetch(`${API}/scrapers`).then(r => r.json());
    const sel = document.getElementById("scraper-select");
    (Array.isArray(scrapers) ? scrapers : []).forEach(name => {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      sel.appendChild(opt);
    });
  } catch {}
}

// ── Run history ───────────────────────────────────────────────────────────────
async function loadRuns() {
  try {
    const runs = await fetch(`${API}/runs`).then(r => r.json());
    const ul = document.getElementById("run-list");
    ul.innerHTML = "";
    (Array.isArray(runs) ? runs : []).forEach(run => {
      const li = document.createElement("li");
      li.className = "run-item";
      const finishedAt = run.finished_at ? new Date(run.finished_at).toLocaleString() : "—";
      const statusCls = run.finished_at ? "done" : "running";
      li.innerHTML = `
        <div class="run-id">${run.run_id}</div>
        <div class="run-meta">
          <span class="pill ${statusCls}">${run.finished_at ? "done" : "running"}</span>
          ${run.jobs_new ?? 0} new · ${run.enriched ?? 0} enriched
        </div>
        <div class="run-id" style="margin-top:2px">${finishedAt}</div>
      `;
      ul.appendChild(li);
    });
  } catch {}
}

// ── Run button ────────────────────────────────────────────────────────────────
document.getElementById("run-btn").addEventListener("click", async () => {
  const scraper = document.getElementById("scraper-select").value;
  const dryRun  = document.getElementById("dry-run").checked;

  // Cancel any existing SSE
  if (activeSSE) { activeSSE.close(); activeSSE = null; }

  clearLogs();
  setBadge("running", "Running…");

  const params = new URLSearchParams();
  if (scraper)  params.set("scraper", scraper);
  if (dryRun)   params.set("dry_run", "true");

  let res;
  try {
    res = await fetch(`${API}/run?${params}`, { method: "POST" });
  } catch (e) {
    appendLog(`ERROR Could not reach server: ${e}`, "error");
    setBadge("error", "Error");
    return;
  }

  if (res.status === 409) {
    appendLog("ERROR A run is already in progress.", "error");
    setBadge("error", "Busy");
    return;
  }
  if (!res.ok) {
    appendLog(`ERROR Server returned ${res.status}`, "error");
    setBadge("error", "Error");
    return;
  }

  const { run_id } = await res.json();
  activeRunId = run_id;
  document.getElementById("log-title").textContent = `Logs — ${run_id}`;

  await loadStatus();
  streamLogs(run_id);
});

// ── SSE log streaming ─────────────────────────────────────────────────────────
function streamLogs(runId) {
  const sse = new EventSource(`${API}/run/${runId}/logs`);
  activeSSE = sse;

  sse.onmessage = (e) => {
    const line = e.data;
    if (line === "__DONE__") {
      sse.close();
      activeSSE = null;
      setBadge("done", "Done");
      loadStatus();
      loadRuns();
      return;
    }
    const lvl = line.startsWith("ERROR") ? "error"
              : line.startsWith("WARNING") ? "warn"
              : line.startsWith("DEBUG")   ? "debug"
              : "info";
    appendLog(line, lvl);
  };

  sse.onerror = () => {
    sse.close();
    activeSSE = null;
    setBadge("error", "Disconnected");
  };
}

// ── Log helpers ───────────────────────────────────────────────────────────────
function appendLog(text, level = "info") {
  const pre = document.getElementById("log-output");
  const span = document.createElement("span");
  span.className = `line-${level}`;
  span.textContent = text + "\n";
  pre.appendChild(span);
  pre.parentElement.scrollTop = pre.parentElement.scrollHeight;
}

function clearLogs() {
  document.getElementById("log-output").innerHTML = "";
  setBadge("", "");
  document.getElementById("log-title").textContent = "Logs";
}

function setBadge(cls, text) {
  const b = document.getElementById("run-badge");
  b.className = "badge " + cls;
  b.textContent = text;
}
