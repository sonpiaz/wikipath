const fromEl = document.getElementById("from");
const toEl = document.getElementById("to");
const goBtn = document.getElementById("go");
const pathEl = document.getElementById("path");
const pathMetaEl = document.getElementById("path-meta");
const logEl = document.getElementById("log");
const datalist = document.getElementById("people");

let people = new Set();

async function loadPeople() {
  try {
    const r = await fetch("/api/people");
    if (!r.ok) throw new Error("status " + r.status);
    const names = await r.json();
    people = new Set(names);
    datalist.innerHTML = names.map(n => `<option value="${escape(n)}"></option>`).join("");
    log("loaded " + names.length + " people", "dim");
  } catch (err) {
    log("failed to load people: " + err.message, "error");
  }
}

function escape(s) {
  return s.replace(/[<>&"]/g, c => ({"<":"&lt;",">":"&gt;","&":"&amp;","\"":"&quot;"}[c]));
}

function refreshButton() {
  const ok = people.has(fromEl.value.trim()) && people.has(toEl.value.trim()) && fromEl.value.trim() !== toEl.value.trim();
  goBtn.disabled = !ok;
}

[fromEl, toEl].forEach(el => el.addEventListener("input", refreshButton));

function log(text, cls = "info") {
  const li = document.createElement("li");
  li.className = cls;
  li.textContent = text;
  logEl.appendChild(li);
  logEl.scrollTop = logEl.scrollHeight;
}

function clearOutput() {
  pathEl.innerHTML = "";
  pathMetaEl.textContent = "";
  logEl.innerHTML = "";
}

let activeStream = null;

goBtn.addEventListener("click", () => {
  if (activeStream) activeStream.close();
  clearOutput();
  goBtn.disabled = true;
  goBtn.textContent = "Searching…";

  const from = fromEl.value.trim();
  const to = toEl.value.trim();
  log(`searching: ${from} → ${to}`, "info");

  const url = `/api/search?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`;
  const es = new EventSource(url);
  activeStream = es;

  es.addEventListener("hello", () => {
    log("connected, BFS starting", "dim");
  });

  es.addEventListener("level", (e) => {
    try {
      const ev = JSON.parse(e.data);
      log(`level ${ev.level}: explored ${ev.nodes.length} new nodes`, "info");
    } catch (err) {
      log("bad level event: " + err.message, "error");
    }
  });

  es.addEventListener("path", (e) => {
    try {
      const ev = JSON.parse(e.data);
      pathEl.innerHTML = "";
      ev.path.forEach((name, i) => {
        const li = document.createElement("li");
        li.textContent = name;
        if (i === 0) li.classList.add("start");
        if (i === ev.path.length - 1) li.classList.add("end");
        pathEl.appendChild(li);
      });
      pathMetaEl.textContent = `${ev.length} nodes (${ev.length - 1} hops)`;
      log(`path found: ${ev.path.join(" → ")}`, "success");
    } catch (err) {
      log("bad path event: " + err.message, "error");
    }
  });

  es.addEventListener("error", (e) => {
    if (e.data) {
      try {
        const msg = JSON.parse(e.data);
        log("error: " + msg, "error");
      } catch {
        log("error event", "error");
      }
    }
  });

  es.addEventListener("done", () => {
    es.close();
    activeStream = null;
    goBtn.textContent = "Start search";
    refreshButton();
  });
});

loadPeople();
