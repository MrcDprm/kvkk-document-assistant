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
  const t = (key, values) => {
    let text = texts[key] || key;
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
      `${t("doc.summary", { count: data.masked_count })} · ${t("doc.chars", { count: data.chars.toLocaleString(document.documentElement.lang) })}`;
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
}

document.addEventListener("DOMContentLoaded", () => {
  setupThemeToggle();
  setupFilePicker();
  setupDocument();
});
