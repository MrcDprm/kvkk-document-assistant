// Page behaviour: theme toggle, file picker label, and the document view.
// Document text is personal data from the user, so it is only ever inserted with
// textContent / createElement, never as HTML.

"use strict";

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// --- Theme ---

function setupThemeToggle() {
  const button = document.querySelector("[data-theme-toggle]");
  if (!button) return;
  button.addEventListener("click", () => {
    const root = document.documentElement;
    const current = root.getAttribute("data-theme") ||
      (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch (e) { /* storage blocked */ }
  });
}

// --- Upload form ---

function setupBusyButton() {
  // Analysis can take a while on the small server: show that something is happening.
  const form = document.querySelector("form.intake");
  if (!form) return;
  form.addEventListener("submit", () => {
    const button = form.querySelector("[data-busy]");
    button.dataset.label = button.textContent;
    button.disabled = true;
    button.textContent = button.dataset.busy;
    button.classList.add("is-busy");
  });
  // Coming back with the browser's back button restores the page from cache: reset the button.
  window.addEventListener("pageshow", (e) => {
    if (!e.persisted) return;
    const button = form.querySelector("[data-busy]");
    button.disabled = false;
    button.classList.remove("is-busy");
    button.textContent = button.dataset.label || button.textContent;
  });
}

function setupFilePicker() {
  const input = document.getElementById("file");
  const label = document.querySelector("[data-file-name]");
  const zone = document.querySelector(".dropzone");
  if (!input || !label || !zone) return;

  const show = () => { label.textContent = input.files.length ? input.files[0].name : ""; };
  input.addEventListener("change", show);

  // Drag and drop onto the dashed area fills the same <input type="file">.
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("is-dragover"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("is-dragover"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("is-dragover");
    if (e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      document.getElementById("mode-file").checked = true;
      show();
    }
  });
}

// --- Document view ---

function setupDocument() {
  const root = document.querySelector("[data-document]");
  if (!root) return;
  const texts = JSON.parse(document.getElementById("i18n").textContent);
  const lang = document.documentElement.lang;
  const t = (key, values) => {
    let text = texts[key] || "";
    for (const [name, value] of Object.entries(values || {})) text = text.replace(`{${name}}`, value);
    return text;
  };
  const parts = {
    filename: root.querySelector("[data-filename]"),
    summary: root.querySelector("[data-summary]"),
    legend: root.querySelector("[data-legend]"),
    original: root.querySelector("[data-original]"),
    masked: root.querySelector("[data-masked]"),
    findings: root.querySelector("[data-findings]"),
  };

  function renderSegments(container, segments, tokens) {
    const fragment = document.createDocumentFragment();
    for (const s of segments) {
      if (!s.type) {
        fragment.append(document.createTextNode(s.text));
        continue;
      }
      const mark = el("mark", `ent ent-${s.type}${s.excluded ? " is-excluded" : ""}${tokens ? " token" : ""}`, s.text);
      mark.title = t(`type.${s.type}`);
      fragment.append(mark);
    }
    container.replaceChildren(fragment);
  }

  function renderLegend(counts) {
    const items = Object.entries(counts).map(([type, count]) => {
      const li = el("li");
      li.append(el("span", `swatch ent-${type}`), el("span", "", t(`type.${type}`)), el("b", "", String(count)));
      return li;
    });
    parts.legend.replaceChildren(...items);
  }

  function renderFindings(findings) {
    if (!findings.length) {
      const row = el("tr");
      const cell = el("td", "empty", t("doc.none"));
      cell.colSpan = 4;
      row.append(cell);
      parts.findings.replaceChildren(row);
      return;
    }
    const rows = findings.map((e) => {
      const row = el("tr", e.excluded ? "is-excluded" : "");
      const type = el("td");
      const chip = el("span", "type-chip");
      chip.append(el("span", `swatch ent-${e.type}`), document.createTextNode(t(`type.${e.type}`)));
      type.append(chip);

      const action = el("td");
      const button = el("button", "btn btn--ghost btn--small", e.excluded ? t("doc.include") : t("doc.exclude"));
      button.type = "button";
      button.dataset.key = e.key;
      button.setAttribute("aria-pressed", String(e.excluded));
      button.addEventListener("click", () => toggle(e.key, button));
      action.append(button);

      const value = el("td", "value", e.text);
      if (e.count > 1) value.append(el("span", "count", `×${e.count}`));
      row.append(type, value, el("td", "token", e.excluded ? t("doc.excluded") : e.token), action);
      return row;
    });
    parts.findings.replaceChildren(...rows);
  }

  function render(data) {
    parts.filename.textContent = data.filename;
    parts.summary.textContent =
      `${t("doc.summary", { count: data.masked_count })} · ${t("doc.chars", { count: data.chars.toLocaleString(lang) })} · ${t(`doc.detector.${data.detector}`)}`;
    renderLegend(data.counts);
    renderSegments(parts.original, data.original, false);
    renderSegments(parts.masked, data.masked, true);
    renderFindings(data.findings);
  }

  function handle(response) {
    if (response.status === 404) {
      window.location.href = "/?error=expired";
      return null;
    }
    if (!response.ok) throw new Error(String(response.status));
    return response.json();
  }

  function fail() {
    parts.summary.textContent = t("doc.load_error");
  }

  async function toggle(key, button) {
    button.disabled = true;
    try {
      const data = await fetch(`/api/tokens/${encodeURIComponent(key)}/toggle`, { method: "POST" }).then(handle);
      if (data) {
        render(data);
        // The table was rebuilt; keep keyboard focus on the same row's button.
        const again = parts.findings.querySelector(`[data-key="${CSS.escape(key)}"]`);
        if (again) again.focus();
      }
    } catch (e) {
      fail();
      button.disabled = false;
    }
  }

  fetch("/api/document").then(handle).then((data) => data && render(data)).catch(fail);

  // --- Audit log ---

  const auditList = root.querySelector("[data-audit]");

  function renderAudit(entries) {
    if (!entries.length) {
      auditList.replaceChildren(el("li", "empty", t("audit.empty")));
      return;
    }
    auditList.replaceChildren(...entries.map((a) => {
      const item = el("li");
      const details = el("details", "audit__item");
      const summary = el("summary");
      const meta = [t("audit.chars", { count: a.chars.toLocaleString(lang) })];
      if (a.input_tokens !== null) meta.push(t("audit.tokens", { input: a.input_tokens, output: a.output_tokens }));
      meta.push(t("audit.ms", { ms: a.latency_ms }));
      if (a.model) meta.push(a.model);
      summary.append(el("span", "audit__kind", t(`audit.kind.${a.kind}`)), el("span", "audit__meta", meta.join(" · ")));
      details.append(summary, el("pre", "audit__sent", a.sent_text));
      item.append(details);
      return item;
    }));
  }

  function loadAudit() {
    fetch("/api/audit").then(handle).then((data) => data && renderAudit(data.entries)).catch(() => {});
  }

  loadAudit();

  // --- Questions ---

  const form = root.querySelector("[data-ask]");
  if (!form) return;
  const qa = root.querySelector("[data-qa]");
  const input = form.querySelector("textarea");
  const submit = form.querySelector("button[type=submit]");

  function bubble(who, text, className) {
    const item = el("li", `qa__item ${className}`);
    item.append(el("span", "qa__who", who), el("p", "qa__text", text));
    qa.append(item);
    return item;
  }

  function addAnswer(item, data) {
    item.querySelector(".qa__text").textContent = data.answer;
    const seconds = (data.usage.latency_ms / 1000).toLocaleString(lang, { maximumFractionDigits: 1 });
    const meta = t("ask.meta", { input: data.usage.input_tokens, output: data.usage.output_tokens, seconds });
    item.append(el("p", "qa__meta", data.usage.model ? `${meta} · ${data.usage.model}` : meta));

    const sources = el("details", "qa__details");
    sources.append(el("summary", "", `${t("ask.sources")} (${data.sources.length})`));
    const list = el("ol", "qa__sources");
    for (const s of data.sources) {
      const li = el("li");
      li.append(el("span", "qa__n", `[${s.n}]`), el("span", "", s.text));
      list.append(li);
    }
    sources.append(list);

    const modelView = el("details", "qa__details");
    modelView.append(
      el("summary", "", t("ask.model_view")),
      el("pre", "audit__sent", `${data.question_masked}\n\n${data.answer_masked}`),
    );
    item.append(sources, modelView);
  }

  function showError(item, code) {
    item.classList.remove("is-pending");
    item.classList.add("is-error");
    item.querySelector(".qa__text").textContent = t(`ask.error.${code}`) || t("ask.error.unavailable");
  }

  async function send(question) {
    question = question.trim();
    if (!question) { input.focus(); return; }
    bubble(t("ask.you"), question, "qa__item--you");
    const answer = bubble(t("ask.assistant"), t("ask.thinking"), "qa__item--bot is-pending");
    input.value = "";
    submit.disabled = true;
    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (response.status === 404) { window.location.href = "/?error=expired"; return; }
      const data = await response.json().catch(() => ({ error: "unavailable" }));
      if (!response.ok) { showError(answer, data.error); return; }
      answer.classList.remove("is-pending");
      addAnswer(answer, data);
      loadAudit();
    } catch (e) {
      showError(answer, "unavailable");
    } finally {
      submit.disabled = false;
    }
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });
  // Enter sends, Shift+Enter makes a new line.
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(input.value); }
  });
  for (const chip of root.querySelectorAll("[data-example]")) {
    chip.addEventListener("click", () => send(chip.textContent));
  }
}

document.addEventListener("DOMContentLoaded", () => {
  setupThemeToggle();
  setupFilePicker();
  setupBusyButton();
  setupDocument();
});
