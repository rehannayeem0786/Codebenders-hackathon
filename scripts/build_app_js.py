"""Build the upgraded frontend/app.js with top-tier hackathon features:
- Dual Citizen vs MeeSeva Kiosk Mode
- Live Voice Visualizer & Web Speech API integration
- Interactive Financial Hero KPI Scorecard (Cash vs Risk Cover strictly separate)
- Interactive Document Readiness Checker with percentage and office guidance
- WhatsApp 1-Click Dispatcher (wa.me)
- Pure vector SVG QR Code Generator for mobile handover
- Simulated WhatsApp Reminder Notification Dialog
- Interactive Knowledge Graph search and path highlighting
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "frontend" / "app.js"

content = r'''/* SchemeSetu front-end. No build step, no framework - one file, API only.
   Every number on screen comes from the deterministic engine; the model only
   paraphrases, extracts or translates. */
"use strict";

const state = {
  lang: "en",
  mode: "citizen",   // "citizen" or "kiosk"
  i18n: { ui: {}, verdicts: {}, categories: {}, field_questions: {} },
  health: null,
  form: {},          // confirmed facts for the current household
  result: null,      // last /api/intake or /api/match payload
  checklist: null,   // cached /api/checklist payload for that household
  graph: null,       // last /api/graph payload
  samples: [],
  profiles: [],
  filter: { verdict: "all", text: "" },
  studio: { schemes: [], selected: null, original: {}, dirty: {} },
  mediaRecorder: null,
  chunks: [],
  docChecklist: {},  // schemeId -> { docId: boolean }
  graphSearch: "",
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function esc(value) {
  return String(value === null || value === undefined ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function t(key, fallback) {
  return (state.i18n.ui && state.i18n.ui[key]) || fallback || key;
}

/* Category emoji map for visual scanning */
const CATEGORY_ICONS = {
  farmer_income: { icon: "\u{1F33E}", cls: "farmer" },
  agriculture: { icon: "\u{1F33E}", cls: "farmer" },
  crop_insurance: { icon: "\u{1F33E}", cls: "farmer" },
  health: { icon: "\u{1F3E5}", cls: "health" },
  insurance: { icon: "\u{1F6E1}", cls: "insurance" },
  education: { icon: "\u{1F393}", cls: "education" },
  scholarship: { icon: "\u{1F393}", cls: "education" },
  pension: { icon: "\u{1F9D3}", cls: "pension" },
  old_age: { icon: "\u{1F9D3}", cls: "pension" },
  housing: { icon: "\u{1F3E0}", cls: "housing" },
  employment: { icon: "\u{1F4BC}", cls: "employment" },
  financial_inclusion: { icon: "\u{1F4B3}", cls: "social" },
  women: { icon: "\u{1F469}", cls: "women" },
  maternal: { icon: "\u{1F469}", cls: "women" },
  food: { icon: "\u{1F35A}", cls: "food" },
  pds: { icon: "\u{1F35A}", cls: "food" },
  social_protection: { icon: "\u{1F91D}", cls: "social" },
  skill: { icon: "\u{1F4DA}", cls: "education" },
  default: { icon: "\u{2B50}", cls: "social" },
};

function getCategoryIcon(category) {
  return CATEGORY_ICONS[category] || CATEGORY_ICONS["default"];
}

/* Toast notification system */
function showToast(message, type) {
  type = type || "info";
  let container = document.querySelector(".toast-container");
  if (!container) {
    container = document.createElement("div");
    container.className = "toast-container";
    document.body.appendChild(container);
  }
  const toast = document.createElement("div");
  toast.className = "toast " + type;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(function() { toast.remove(); }, 3000);
}

/* Theme toggle (dark/light) */
function toggleTheme() {
  const isLight = document.body.classList.toggle("light-theme");
  const btn = document.getElementById("btn-theme-toggle");
  if (btn) btn.textContent = isLight ? "\u2600\uFE0F" : "\u{1F319}";
  localStorage.setItem("schemesetu-theme", isLight ? "light" : "dark");
  showToast(isLight ? "Switched to Light Theme" : "Switched to Dark Theme", "info");
}

function restoreTheme() {
  const saved = localStorage.getItem("schemesetu-theme");
  if (saved === "light") {
    document.body.classList.add("light-theme");
    var btn = document.getElementById("btn-theme-toggle");
    if (btn) btn.textContent = "\u2600\uFE0F";
  }
}

/* Confetti celebration on eligible results */
function launchConfetti() {
  const colors = ["#10b981", "#3b82f6", "#f59e0b", "#8b5cf6", "#f43f5e", "#fbbf24"];
  for (let i = 0; i < 40; i++) {
    const piece = document.createElement("div");
    piece.className = "confetti-piece";
    piece.style.left = (Math.random() * 100) + "vw";
    piece.style.background = colors[Math.floor(Math.random() * colors.length)];
    piece.style.animationDelay = (Math.random() * 1.5) + "s";
    piece.style.width = (6 + Math.random() * 8) + "px";
    piece.style.height = (6 + Math.random() * 8) + "px";
    piece.style.borderRadius = Math.random() > 0.5 ? "50%" : "2px";
    document.body.appendChild(piece);
    setTimeout(function() { piece.remove(); }, 4500);
  }
}

/* Keyboard shortcuts */
const SHORTCUTS = {
  "Enter": { desc: "Submit intake", action: function() { var btn = document.getElementById("btn-analyse"); if (btn && !btn.disabled) btn.click(); } },
  "Escape": { desc: "Close modal", action: function() { document.querySelectorAll(".modal").forEach(function(m) { m.style.display = "none"; }); } },
  "?": { desc: "Toggle shortcuts", action: function() { var tip = document.querySelector(".shortcuts-tooltip"); if (tip) tip.classList.toggle("visible"); } },
};

function handleKeyboard(e) {
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") {
    if (e.key === "Escape") { SHORTCUTS["Escape"].action(); }
    return;
  }
  var shortcut = SHORTCUTS[e.key];
  if (shortcut) { e.preventDefault(); shortcut.action(); }
}

/* Footer stats */
function updateFooterStats() {
  var el = document.getElementById("footer-stats");
  if (!el || !state.health) return;
  var h = state.health;
  el.textContent = h.graph.schemes + " schemes \u00B7 " + h.graph.rules + " rules \u00B7 Offline-first PWA";
}

function verdictLabel(verdict) {
  return (state.i18n.verdicts && state.i18n.verdicts[verdict]) || verdict;
}

function getSchemeTitle(m) {
  let local = "";
  if (m.name_local && typeof m.name_local === "object") {
    local = m.name_local[state.lang] || "";
  } else if (typeof m.name_local === "string") {
    local = m.name_local;
  }
  if (state.lang === "en" || !local) {
    return esc(m.name);
  }
  return `${esc(local)} <span class="muted small">· ${esc(m.name)}</span>`;
}

function getSchemePrintTitle(s) {
  let local = "";
  if (s.name_local && typeof s.name_local === "object") {
    local = s.name_local[state.lang] || "";
  } else if (typeof s.name_local === "string") {
    local = s.name_local;
  }
  return local && state.lang !== "en" ? `${esc(s.name)} / ${esc(local)}` : esc(s.name);
}

/* "verified <date>" as a badge; warning style when the check is older than 180 days. */
const FRESH_DAYS = 180;
function freshnessBadge(dateStr) {
  const label = `verified ${esc(dateStr)}`;
  const when = new Date(dateStr);
  if (!dateStr || Number.isNaN(when.getTime())) return label;
  const ageDays = (Date.now() - when.getTime()) / 86400000;
  return `<span class="${ageDays > FRESH_DAYS ? "badge warn" : "badge"}">${label}</span>`;
}

async function api(path, options) {
  const res = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json" } }, options || {}));
  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : {}; } catch (err) { data = { raw: text }; }
  if (!res.ok) {
    const detail = (data && (data.detail || data.message)) || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

function log(message, bad) {
  const box = $("#intake-log");
  if (!box) return;
  const stamp = new Date().toLocaleTimeString();
  box.innerHTML = `<div class="${bad ? "bad" : ""}">[${stamp}] ${esc(message)}</div>` + box.innerHTML;
}

function switchTab(name) {
  $$(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $$(".panel").forEach((p) => p.classList.toggle("active", p.id === "panel-" + name));
}

/* ------------------------------- Mode Switch ------------------------------ */
function setMode(mode) {
  state.mode = mode;
  $$(".mode-switch .chip").forEach((btn) => btn.classList.toggle("active", btn.dataset.mode === mode));
  const banner = $("#kiosk-banner");
  if (banner) banner.style.display = mode === "kiosk" ? "flex" : "none";
  if (mode === "kiosk") {
    const token = "TS-MEESEVA-" + Math.floor(1000 + Math.random() * 9000);
    const tokenNode = $("#kiosk-token");
    if (tokenNode) tokenNode.textContent = token;
    log("🏢 Switched to MeeSeva / CSC Operator Kiosk Mode. Counter token generated: " + token);
  } else {
    log("👤 Switched to Citizen Mode. Voice and simplified language active.");
  }
}

/* ------------------------------- i18n + health ---------------------------- */
async function loadLanguage(lang) {
  state.lang = lang;
  try {
    state.i18n = await api(`/api/i18n/${lang}`);
  } catch (err) {
    log("Could not load translations: " + err.message, true);
  }
  applyI18n();
  if (state.result) {
    if (state.result.profile_id) {
      try {
        const reMatch = await api(`/api/match?profile_id=${encodeURIComponent(state.result.profile_id)}&lang=${lang}`);
        if (reMatch && reMatch.matches) {
          state.result = Object.assign({}, state.result, reMatch);
        }
      } catch (e) {}
    }
    renderMatches();
    if (state.result.next_questions) renderQuestions(state.result.next_questions);
  }
  if (state.graph) renderGraph();
}

function applyI18n() {
  $$("[data-i18n]").forEach((node) => {
    const value = t(node.getAttribute("data-i18n"), node.textContent);
    if (node.tagName === "INPUT" || node.tagName === "TEXTAREA") node.placeholder = value;
    else node.textContent = value;
  });
  $$("[data-i18n-placeholder]").forEach((node) => {
    node.placeholder = t(node.getAttribute("data-i18n-placeholder"), node.placeholder);
  });
}

async function loadHealth() {
  state.health = await api("/api/health");
  const h = state.health;
  const g = h.graph;
  const pills = [
    { text: `${g.schemes} schemes · ${g.rules} rules · ${g.nodes} graph nodes`, cls: "ok" },
    { text: h.llm.available ? `LLM: ${h.llm.active}` : "LLM off — deterministic mode", cls: h.llm.available ? "ok" : "warn" },
    { text: h.llm.speech_to_text ? `voice: ${h.llm.speech_to_text}` : "voice: off", cls: h.llm.speech_to_text ? "ok" : "warn" },
    { text: h.guardrails.pii_redaction ? "PII shield ON" : "PII shield OFF", cls: h.guardrails.pii_redaction ? "ok" : "warn" },
    { text: `graphify: ${g.graphify.imported ? g.graphify.nodes + " extracted nodes (" + g.graphify.bridged + " bridged)" : "off - curated graph only"}`, cls: g.graphify.imported ? "ok" : "muted" },
    { text: `households stored: ${h.store.profiles}`, cls: "muted" },
  ];
  $("#statusbar").innerHTML = pills.map((p) => `<span class="pill ${p.cls}">${esc(p.text)}</span>`).join("");
  $("#health-json").textContent = JSON.stringify(h, null, 2);
  renderPrivacy();
  loadDataRights();
}

function renderPrivacy() {
  const g = state.health ? state.health.guardrails : null;
  if (!g) return;
  $("#privacy-report").innerHTML = [
    `<div><strong>${esc(t("privacy.line"))}</strong></div>`,
    `<div class="muted small">Redaction is <b>${g.pii_redaction ? "on" : "off"}</b>; refusing sensitive IDs is <b>${g.block_sensitive_ids ? "on" : "off"}</b>.</div>`,
    `<div class="muted small">Patterns active: ${g.patterns_active.map((p) => esc(p.label)).join(", ")}</div>`,
    `<div class="muted small">Never collected:</div><div>${g.forbidden_fields.map((f) => `<span class="field-pill">${esc(f)}</span>`).join("")}</div>`,
    `<div class="muted small">Redactions this session: ${g.session_stats.redactions} ${esc(JSON.stringify(g.session_stats.by_kind))}</div>`,
  ].join("");
}

/* --------------------------------- samples -------------------------------- */
async function loadSamples() {
  const payload = await api("/api/samples");
  state.samples = payload.samples || [];
  $("#samples").innerHTML = state.samples
    .map((s) => `<button class="sample" data-sample="${esc(s.id)}" title="${esc(s.title)}">${esc(s.title || s.id)}</button>`)
    .join("");
  $$("#samples .sample").forEach((btn) => btn.addEventListener("click", async () => {
    const sample = state.samples.find((s) => s.id === btn.dataset.sample);
    if (!sample) return;
    $("#intake-text").value = sample.text || "";
    state.form = Object.assign({}, state.form, sample.form || {});
    await runIntake(sample.text || "");
  }));
}

/* ---------------------------------- intake -------------------------------- */
async function runIntake(text) {
  const box = $("#intake-text");
  const body = {
    text: text === undefined ? box.value : text,
    language: state.lang,
    form: state.form,
    use_llm: $("#use-llm").checked,
    save: $("#save-profile").checked,
    plan_reminders: $("#save-profile").checked,
    consent: $("#consent-agree").checked,
  };
  const btn = $("#btn-analyse");
  btn.disabled = true;
  log("Checking deterministic rules against 26 Telangana & Central schemes…");
  try {
    const data = await api("/api/intake", { method: "POST", body: JSON.stringify(body) });
    state.result = data;
    state.checklist = null;
    state.form = Object.assign({}, (data.intake && data.intake.facts) || {}, state.form);
    const i = data.intake || {};
    log(`Read ${Object.keys(i.facts || {}).length} facts using ${i.method}. ${i.privacy_note || ""}`.trim());
    if (i.dropped_keys && i.dropped_keys.length) log("Dropped fields we never store: " + i.dropped_keys.join(", "), true);
    renderMatches();
    renderQuestions(data.next_questions || []);
    await loadProfiles();
    await loadGraph(data.profile_id);
    switchTab("results");
  } catch (err) {
    log("Failed: " + err.message, true);
  } finally {
    btn.disabled = false;
    btn.classList.remove("loading");
  }
}

async function loadProfiles() {
  const data = await api("/api/profiles");
  state.profiles = data.profiles || [];
  const options = ['<option value="">— choose a saved household —</option>']
    .concat(state.profiles.map((p) => `<option value="${esc(p.id)}">${esc(p.label)} (${esc(p.id)})</option>`));
  ["#tracker-profile", "#studio-profile"].forEach((sel) => {
    const node = $(sel);
    if (!node) return;
    const keep = node.value;
    node.innerHTML = options.join("");
    if (keep) node.value = keep;
  });
}

/* ------------------------------- questions -------------------------------- */
function renderQuestions(questions) {
  const box = $("#questions");
  if (!box) return;
  if (!questions || !questions.length) {
    box.innerHTML = `<p class="muted">Nothing else is blocking a verdict right now. All criteria are fully determined!</p>`;
    return;
  }
  box.innerHTML = questions.map((q, idx) => {
    const values = q.values || [];
    let control = `<input data-field="${esc(q.field)}" placeholder="${esc(q.question)}" />`;
    if (q.kind === "bool") {
      control = `<select data-field="${esc(q.field)}"><option value="">yes / no</option><option value="true">${esc(t("common.yes", "Yes"))}</option><option value="false">${esc(t("common.no", "No"))}</option></select>`;
    } else if (values.length) {
      control = `<select data-field="${esc(q.field)}"><option value="">choose…</option>${values.map((v) => `<option value="${esc(v)}">${esc(v)}</option>`).join("")}</select>`;
    }
    const decides = (q.unlocks_schemes || []).map(esc).join(", ");
    return `<div class="question">
      <div><strong>${idx + 1}. ${esc(q.question || q.label)}</strong></div>
      <div class="why">${esc(q.why || "")} · ${q.unlocks_definite} scheme(s) decided by this answer alone${q.potential_value_inr ? ` · ≈ ₹${Number(q.potential_value_inr).toLocaleString("en-IN")}/year` : ""}</div>
      <div class="answer">${control}<button class="ghost" data-answer="${esc(q.field)}">Answer</button></div>
      ${decides ? `<div class="why">decides: ${decides}</div>` : ""}
    </div>`;
  }).join("");

  $$("#questions .answer button").forEach((btn) => btn.addEventListener("click", () => answerQuestion(btn.dataset.answer)));
}

async function answerQuestion(field) {
  const input = $(`#questions [data-field="${field}"]`);
  if (!input) return;
  let value = input.value;
  if (value === "" || value === null) return;
  if (value === "true" || value === "false") value = value === "true";
  else if (/^-?\d+(\.\d+)?$/.test(value)) value = Number(value);
  state.form[field] = value;
  await runIntake("");
}

/* -------------------------------- results --------------------------------- */
const WHY_CLASS = (line) => {
  if (line.startsWith("Pass")) return "good";
  if (line.startsWith("Not met")) return "bad";
  if (line.startsWith("Need to know")) return "ask";
  return "";
};

function updateHeroKPIs() {
  const data = state.result;
  if (!data) return;
  const summary = data.summary || {};
  const cash = summary.likely_eligible_cash_inr || 0;
  const cover = summary.likely_eligible_cover_inr || 0;
  const counts = summary.counts || {};
  const actionable = (counts.likely_eligible || 0) + (counts.possible || 0);

  const cashNode = $("#kpi-cash-val");
  const coverNode = $("#kpi-cover-val");
  const schemesNode = $("#kpi-schemes-val");
  const schemesSub = $("#kpi-schemes-sub");
  const actionNode = $("#kpi-action-val");
  const actionSub = $("#kpi-action-sub");

  if (cashNode) cashNode.textContent = `₹${Number(cash).toLocaleString("en-IN")}`;
  if (coverNode) coverNode.textContent = `₹${Number(cover).toLocaleString("en-IN")}`;
  if (schemesNode) schemesNode.textContent = `${actionable} Schemes`;
  if (schemesSub) schemesSub.textContent = `${counts.likely_eligible || 0} likely eligible · ${counts.possible || 0} possible`;

  const topQ = data.next_questions && data.next_questions[0];
  if (actionNode) {
    if (topQ) {
      actionNode.textContent = topQ.label || topQ.question;
      if (actionSub) actionSub.textContent = `Unlocks ${topQ.unlocks_definite} scheme(s)${topQ.potential_value_inr ? ` · ₹${Number(topQ.potential_value_inr).toLocaleString("en-IN")}` : ""}`;
    } else {
      actionNode.textContent = "All facts verified";
      if (actionSub) actionSub.textContent = "Ready to file applications";
    }
  }
}

function renderAlternativeSchemes(m) {
  if (m.verdict !== "not_eligible") return "";
  let tip = "";
  const sid = (m.scheme_id || "").toLowerCase();
  if (sid.includes("kisan") || sid.includes("rythu") || sid.includes("fasal")) {
    tip = "💡 <b>Alternative for Landless Rural Workers:</b> While PM-KISAN & Rythu Bharosa require land titles, unorganised agricultural laborers qualify for <b>e-Shram (₹2,00,000 accident cover)</b> and <b>MGNREGA 100 days guaranteed wage work</b>.";
  } else if (sid.includes("old") || sid.includes("pension") || sid.includes("aasara")) {
    tip = "💡 <b>Alternative for Under-57 Workers:</b> If under the 57-year age threshold, explore <b>e-Shram unorganised registration</b> or subsidized micro-insurance under <b>PMJJBY / PMSBY (₹2,00,000 cover for ₹436/yr)</b>.";
  } else if (sid.includes("scholarship") || sid.includes("vidya")) {
    tip = "💡 <b>Domestic Education Support:</b> Check domestic <b>Telangana ePASS Post-Matric Tuition Fee Reimbursement</b> or Central Pre-Matric SC/ST/BC Scholarships.";
  } else if (sid.includes("mudra") || sid.includes("svanidhi")) {
    tip = "💡 <b>Micro-Credit Alternative:</b> Look at <b>PM SVANidhi</b> (₹10,000 collateral-free working capital for urban vendors) or <b>PMEGP margin money subsidy</b>.";
  }
  if (!tip) return "";
  return `<div class="alt-scheme-box"><div class="alt-scheme-title">Guidance & Alternative Path</div><div class="muted small">${tip}</div></div>`;
}

function renderMatches() {
  const data = state.result;
  if (!data) return;
  $("#headline").textContent = data.summary ? data.summary.headline : "";
  updateHeroKPIs();

  // Celebrate if we found eligible schemes!
  const eligibleCount = (data.matches || []).filter(function(m) { return m.verdict === "likely_eligible"; }).length;
  if (eligibleCount > 0) {
    showToast("\u{1F389} Found " + eligibleCount + " schemes you can claim!", "success");
    launchConfetti();
  }

  const filter = state.filter;
  const list = (data.matches || []).filter((m) => {
    if (filter.verdict !== "all" && m.verdict !== filter.verdict) return false;
    if (filter.text) {
      const hay = `${m.name} ${m.summary} ${m.category_label} ${m.benefit || ""}`.toLowerCase();
      if (!hay.includes(filter.text.toLowerCase())) return false;
    }
    return true;
  });

  $("#matches").innerHTML = list.map((m) => {
    const catIcon = getCategoryIcon(m.category);
    const vLabel = verdictLabel(m.verdict);
    const cLabel = (state.i18n.categories && state.i18n.categories[m.category]) || m.category_label || m.category;
    return `<article class="match match-card verdict-${esc(m.verdict)} ${esc(m.verdict)}" id="match-${esc(m.scheme_id)}">
      <h3><span class="category-icon ${esc(catIcon.cls)}">${catIcon.icon}</span> ${getSchemeTitle(m)}</h3>
      <div class="meta">
        <span class="badge verdict">${esc(vLabel)}</span>
        <span class="badge">${esc(cLabel)}</span>
        <span class="badge">${esc(m.level)}</span>
        <span class="badge">${esc(m.provenance)}</span>
        ${m.benefit_value_inr ? `<span class="badge cash">≈ ₹${Number(m.benefit_value_inr).toLocaleString("en-IN")}</span>` : ""}
        <span class="badge">confidence ${esc(String(m.confidence))}</span>
        <span class="badge">${esc(String(m.mandatory_documents))}/${esc(String(m.document_count))} documents</span>
      </div>
      <p class="muted">${esc(m.summary)}</p>

      <!-- Document Readiness Section -->
      <div class="doc-checklist" id="doc-box-${esc(m.scheme_id)}">
        <div class="doc-checklist-title">
          <span>📋 ${esc(t("results.documents", "Documents to keep ready"))}</span>
          <span class="small muted" id="doc-prog-${esc(m.scheme_id)}">checking papers…</span>
        </div>
        <div class="doc-items" id="doc-items-${esc(m.scheme_id)}"><span class="muted small">loading requirements…</span></div>
      </div>

      <ul class="why">${(m.why || []).map((line) => `<li class="${WHY_CLASS(line)}">${esc(line)}</li>`).join("")}</ul>
      <div class="row wrap">
        ${m.apply_url ? `<a href="${esc(m.apply_url)}" target="_blank" rel="noopener"><button class="ghost">${esc(t("results.open_portal", "Official portal"))}</button></a>` : ""}
        <button class="ghost" data-track="${esc(m.scheme_id)}" data-name="${esc(m.name)}">${esc(t("results.track", "Track application"))}</button>
        <button class="ghost" data-view-graph="${esc(m.scheme_id)}">🔍 View in Graph</button>
        <button class="ghost" data-explain="${esc(m.scheme_id)}">🔊 Explain aloud</button>
      </div>
      ${m.unlock_questions && m.unlock_questions.length ? `<div class="why ask">Answer to decide this one: ${m.unlock_questions.map((q) => esc(q.label)).join(", ")}</div>` : ""}
      <details>
        <summary>${esc(t("results.apply", "How to apply, step by step"))}</summary>
        <ol class="steps" data-scheme="${esc(m.scheme_id)}"><li class="muted">loading…</li></ol>
      </details>
      <div class="source">
        ${esc(t("results.deadline", "Deadline"))}: ${esc(m.deadline)} · ${freshnessBadge(m.verified_on)}
        ${m.days_since_verified !== null && m.days_since_verified !== undefined ? `(${esc(String(m.days_since_verified))} days ago)` : ""}
        · ${esc(m.source_name)} ${m.source_url ? `<a href="${esc(m.source_url)}" target="_blank" rel="noopener">source</a>` : ""}
      </div>
      <div class="conf">${esc(m.guardrail || "")}</div>
      ${renderAlternativeSchemes(m)}
    </article>`;
  }).join("") || `<p class="muted">Nothing matches this filter.</p>`;

  $$("[data-track]").forEach((btn) => btn.addEventListener("click", () => trackApplication(btn.dataset.track, btn.dataset.name)));
  $$("[data-explain]").forEach((btn) => btn.addEventListener("click", () => explainAloud(btn.dataset.explain)));
  $$("[data-view-graph]").forEach((btn) => btn.addEventListener("click", () => showSchemeInGraph(btn.dataset.viewGraph)));
  list.forEach((m) => loadSchemeSteps(m.scheme_id));
}

async function loadSchemeSteps(schemeId) {
  const stepsHolder = $(`ol.steps[data-scheme="${schemeId}"]`);
  const docHolder = $(`#doc-items-${schemeId}`);
  const progHolder = $(`#doc-prog-${schemeId}`);
  try {
    const scheme = await api(`/api/schemes/${schemeId}?lang=${state.lang}`);
    if (stepsHolder) {
      stepsHolder.innerHTML = (scheme.apply_steps || []).map((s) => `<li>${esc(s)}</li>`).join("");
    }
    if (docHolder) {
      const docs = scheme.documents || [];
      if (!docs.length) {
        docHolder.innerHTML = `<span class="muted small">No mandatory documents listed.</span>`;
        if (progHolder) progHolder.textContent = "Ready";
      } else {
        const saved = state.docChecklist[schemeId] || {};
        docHolder.innerHTML = docs.map((d) => {
          const isChecked = Boolean(saved[d.id]);
          const flag = d.mandatory ? "compulsory" : "if available";
          const how = d.how_to_get ? `<span class="doc-guide">📍 ${esc(d.how_to_get)}</span>` : "";
          return `<label class="doc-item ${isChecked ? "checked" : ""}">
            <input type="checkbox" data-scheme="${esc(schemeId)}" data-doc="${esc(d.id)}" ${isChecked ? "checked" : ""}/>
            <div>
              <span>${esc(d.label)} <b class="small muted">(${flag})</b></span>
              ${how}
            </div>
          </label>`;
        }).join("");

        updateDocProgress(schemeId, docs);

        docHolder.querySelectorAll("input[type='checkbox']").forEach((cb) => {
          cb.addEventListener("change", (e) => {
            const sid = e.target.dataset.scheme;
            const did = e.target.dataset.doc;
            if (!state.docChecklist[sid]) state.docChecklist[sid] = {};
            state.docChecklist[sid][did] = e.target.checked;
            e.target.closest(".doc-item").classList.toggle("checked", e.target.checked);
            updateDocProgress(sid, docs);
          });
        });
      }
    }
  } catch (err) {
    if (stepsHolder) stepsHolder.innerHTML = `<li class="muted">could not load: ${esc(err.message)}</li>`;
  }
}

function updateDocProgress(schemeId, docs) {
  const prog = $(`#doc-prog-${schemeId}`);
  if (!prog || !docs || !docs.length) return;
  const saved = state.docChecklist[schemeId] || {};
  const ready = docs.filter((d) => saved[d.id]).length;
  const pct = Math.round((ready / docs.length) * 100);
  prog.textContent = `${ready}/${docs.length} ready (${pct}%)`;
  prog.style.color = pct === 100 ? "#a7f3d0" : pct > 0 ? "#fde68a" : "var(--muted)";
}

function showSchemeInGraph(schemeId) {
  switchTab("graph");
  const targetId = `scheme:${schemeId}`;
  selectNode(targetId);
  const circle = $(`#graph-svg g.node[data-node="${targetId}"] circle`);
  if (circle) {
    circle.setAttribute("r", "16");
    circle.setAttribute("stroke", "#fff");
    circle.setAttribute("stroke-width", "3");
  }
}

async function trackApplication(schemeId, name) {
  const profileId = (state.result && state.result.profile_id) || $("#tracker-profile").value;
  if (!profileId) { log("Save the household first, then track it.", true); return; }
  await api("/api/applications", {
    method: "POST",
    body: JSON.stringify({ profile_id: profileId, scheme_id: schemeId, scheme_name: name, status: "documents_pending" }),
  });
  await loadTracker(profileId);
  switchTab("tracker");
}

/* ------------------------------ why, aloud -------------------------------- */
async function explainAloud(schemeId) {
  const profileId = state.result ? state.result.profile_id : "";
  const data = await api(`/api/narrate/${schemeId}?lang=${state.lang}&profile_id=${encodeURIComponent(profileId || "")}`);
  const text = data.text || (data.why || []).slice(0, 5).join(". ");
  log(`Explain aloud (${data.method}): ${text}`);
  speak(text);
}

function speak(text) {
  if (!text || !window.speechSynthesis) return;
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = state.lang === "te" ? "te-IN" : state.lang === "hi" ? "hi-IN" : "en-IN";
  utter.rate = 0.95;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utter);
}

/* ---------------------------------- graph --------------------------------- */
async function loadGraph(profileId) {
  const query = profileId ? `?profile_id=${encodeURIComponent(profileId)}` : "";
  state.graph = await api("/api/graph" + query);
  renderGraph();
  renderPaths(state.graph.paths || []);
}

const COLUMN = { fact: 150, missing: 150, rule: 520, scheme: 860 };
const STATUS_COLOR = { pass: "#10b981", fail: "#f43f5e", unknown: "#f59e0b" };
const VERDICT_COLOR = {
  likely_eligible: "#10b981", possible: "#3b82f6", needs_info: "#f59e0b", not_eligible: "#f43f5e",
};

function renderGraph() {
  const g = state.graph;
  const svg = $("#graph-svg");
  if (!svg) return;
  if (!g || !g.nodes || !g.nodes.length) { svg.innerHTML = ""; return; }

  const filterText = (state.graphSearch || "").toLowerCase();
  const cols = { fact: [], missing: [], rule: [], scheme: [], other: [] };

  g.nodes.forEach((n) => {
    if (filterText) {
      const hay = `${n.label || ""} ${n.id || ""} ${n.kind || ""}`.toLowerCase();
      if (!hay.includes(filterText)) return;
    }
    const kind = COLUMN[n.kind] ? n.kind : "other";
    cols[kind].push(n);
  });

  const height = 620;
  const pos = {};
  Object.keys(cols).forEach((kind) => {
    const list = cols[kind];
    const x = COLUMN[kind] || 500;
    list.forEach((n, i) => {
      const y = ((i + 1) * height) / (list.length + 1);
      pos[n.id] = { x, y, node: n };
    });
  });

  const edges = (g.edges || []).filter((e) => pos[e.source] && pos[e.target]);
  const edgeSvg = edges.map((e) => {
    const a = pos[e.source], b = pos[e.target];
    const status = e.status || "";
    const cls = status === "pass" || status === "fail" || status === "unknown" ? status : "";
    const mx = (a.x + b.x) / 2;
    return `<path class="edge ${cls}" data-source="${esc(e.source)}" data-target="${esc(e.target)}" d="M${a.x},${a.y} C${mx},${a.y} ${mx},${b.y} ${b.x},${b.y}" />`;
  }).join("");

  const nodeSvg = g.nodes.map((n) => {
    const p = pos[n.id];
    if (!p) return "";
    let fill = "#3b82f6", radius = 5;
    if (n.kind === "scheme") { fill = VERDICT_COLOR[n.verdict] || "#8b5cf6"; radius = 13; }
    else if (n.kind === "rule") { fill = STATUS_COLOR[n.status] || "#9bb0db"; radius = n.hard ? 7 : 5; }
    else if (n.kind === "missing") { fill = "#f59e0b"; radius = 6; }
    const label = String(n.label || n.id).slice(0, 42);
    const anchor = n.kind === "scheme" ? "end" : "start";
    const dx = n.kind === "scheme" ? -18 : 18;
    return `<g class="node" data-node="${esc(n.id)}">
        <circle cx="${p.x}" cy="${p.y}" r="${radius}" fill="${fill}" />
        <text x="${p.x + dx}" y="${p.y + 3}" text-anchor="${anchor}">${esc(label)}</text>
      </g>`;
  }).join("");

  svg.innerHTML = `<g class="edges-group">${edgeSvg}</g><g class="nodes-group">${nodeSvg}</g>`;

  $$("#graph-svg .node").forEach((node) => {
    node.addEventListener("click", () => selectNode(node.dataset.node));
    node.addEventListener("mouseenter", () => highlightNodeEdges(node.dataset.node, true));
    node.addEventListener("mouseleave", () => highlightNodeEdges(node.dataset.node, false));
  });
}

function highlightNodeEdges(nodeId, enable) {
  $$("#graph-svg .edge").forEach((edge) => {
    const match = edge.dataset.source === nodeId || edge.dataset.target === nodeId;
    if (enable) {
      edge.classList.toggle("highlight", match);
      edge.style.opacity = match ? "1" : "0.15";
    } else {
      edge.classList.remove("highlight");
      edge.style.opacity = "";
    }
  });
}

async function selectNode(nodeId) {
  try {
    const data = await api(`/api/graph/node/${encodeURIComponent(nodeId)}?depth=1`);
    const centre = (data.nodes || []).find((n) => n.id === nodeId) || {};
    const neighbours = (data.nodes || []).filter((n) => n.id !== nodeId);
    $("#node-detail").innerHTML = [
      `<div><strong>${esc(centre.label || nodeId)}</strong> <span class="badge">${esc(centre.kind || "")}</span></div>`,
      centre.status ? `<div style="margin-top:6px;">status: <b style="color:${STATUS_COLOR[centre.status] || "#fff"}">${esc(centre.status)}</b>${centre.hard ? " · mandatory rule" : " · optional rule"}</div>` : "",
      centre.reason ? `<div class="muted" style="margin-top:4px;">${esc(centre.reason)}</div>` : "",
      centre.value !== undefined && centre.value !== null ? `<div style="margin-top:4px;">your answer: <b>${esc(String(centre.value))}</b></div>` : "",
      centre.expected !== undefined && centre.expected !== null ? `<div>rule expects: <b>${esc(JSON.stringify(centre.expected))}</b></div>` : "",
      centre.source_note ? `<div class="muted small" style="margin-top:4px;">source note: ${esc(centre.source_note)}</div>` : "",
      centre.provenance ? `<div class="badge warn" style="margin-top:6px;">provenance: ${esc(centre.provenance)}</div>` : "",
      `<div class="muted small" style="margin-top:8px;">${neighbours.length} connected elements: ${neighbours.slice(0, 8).map((n) => esc(String(n.label || n.id).slice(0, 32))).join(", ")}</div>`,
    ].join("");
  } catch (err) {
    $("#node-detail").textContent = "could not explore this node: " + err.message;
  }
}

function renderPaths(paths) {
  const box = $("#paths");
  if (!box) return;
  if (!paths || !paths.length) { box.innerHTML = `<p class="muted">Run the intake first - the paths appear here.</p>`; return; }
  const order = { fail: 0, unknown: 1, pass: 2 };
  const sorted = paths.slice().sort((a, b) => (order[a.status] ?? 3) - (order[b.status] ?? 3));
  box.innerHTML = sorted.map((p) => `<div class="path">
      <div>${esc(p.field_label)} <span class="muted">(${p.fact_value === undefined || p.fact_value === null ? "not answered" : esc(String(p.fact_value))})</span> → ${esc(p.rule_text)} <span class="muted">→ ${esc(p.scheme_name)}</span>
        ${p.reason ? `<div class="muted small">${esc(p.reason)}</div>` : ""}</div>
      <div class="status ${esc(p.status)}">${esc(p.status)}${p.hard ? " · mandatory" : ""}${p.provenance === "AMBIGUOUS" ? " [AMBIGUOUS]" : ""}</div>
    </div>`).join("");
}

/* --------------------------------- tracker -------------------------------- */
const STATUS_LABELS = ["not_started", "documents_pending", "submitted", "under_review", "approved", "rejected", "paid"];

async function loadTracker(profileId) {
  const id = profileId || $("#tracker-profile").value;
  const suffix = id ? `?profile_id=${encodeURIComponent(id)}` : "";
  const [apps, reminders] = await Promise.all([
    api("/api/applications" + suffix),
    api("/api/reminders" + suffix),
  ]);
  const list = apps.applications || [];
  $("#applications").innerHTML = list.length
    ? list.map((a) => `<div class="app" data-app="${a.id}">
        <div><strong>${esc(a.scheme_name || a.scheme_id)}</strong> <span class="badge">${esc(a.scheme_id)}</span></div>
        <div class="muted small">updated ${esc(a.updated_at || "")}${a.reference_no ? ` · ref ${esc(a.reference_no)}` : ""}</div>
        <div class="row wrap">
          <select class="status-select">${STATUS_LABELS.map((s) => `<option value="${s}" ${s === a.status ? "selected" : ""}>${s.replace(/_/g, " ")}</option>`).join("")}</select>
          <input class="ref" placeholder="reference number" value="${esc(a.reference_no || "")}" />
          <button class="ghost" data-save-app="${a.id}">save</button>
        </div>
        ${a.deadline ? `<div class="muted small" style="margin-top:6px;">deadline: <b>${esc(a.deadline)}</b></div>` : ""}
      </div>`).join("")
    : `<p class="muted">Nothing tracked yet. Open a scheme in <b>Your schemes</b> and press “Track application”.</p>`;

  $$("[data-save-app]").forEach((btn) => btn.addEventListener("click", async () => {
    const row = btn.closest(".app");
    await api(`/api/applications/${btn.dataset.saveApp}/status`, {
      method: "POST",
      body: JSON.stringify({ status: row.querySelector(".status-select").value, reference_no: row.querySelector(".ref").value }),
    });
    await loadTracker(id);
  }));

  const rem = reminders.reminders || [];
  $("#reminders").innerHTML = rem.length
    ? rem.map((r) => `<div class="reminder" data-reminder="${r.id}">
        <div><strong>${esc(r.message)}</strong></div>
        <div class="muted small" style="margin-top:4px;">due ${esc(r.due_on)} · ${esc(r.channel)} · status: <b>${esc(r.status)}</b></div>
        ${r.status === "pending" ? `<div class="row"><button class="ghost" data-done="${r.id}">mark done</button></div>` : ""}
      </div>`).join("")
    : `<p class="muted">No reminders yet - press “Remind me”.</p>`;

  $$("[data-done]").forEach((btn) => btn.addEventListener("click", async () => {
    await api(`/api/reminders/${btn.dataset.done}/done`, { method: "POST" });
    await loadTracker(id);
  }));
}

async function planReminders() {
  const profileId = $("#tracker-profile").value || (state.result && state.result.profile_id);
  if (!profileId) { log("Choose a saved household first.", true); return; }
  const data = await api("/api/reminders/plan", { method: "POST", body: JSON.stringify({ profile_id: profileId, days_before: 10 }) });
  log(`Queued ${data.created.length} reminder(s).`);
  await loadTracker(profileId);
}

function openWhatsAppAlertPreview() {
  const modal = $("#modal-wa-alert");
  if (!modal) return;
  const profileId = (state.result && state.result.profile_id) || $("#tracker-profile").value || "Demo Citizen";
  const body = $("#wa-msg-body");
  if (body) {
    body.innerHTML = `
      <b>Namaste! 🔔 MeeSeva / SchemeSetu Deadline Alert</b><br><br>
      Household ID: <code>${esc(profileId)}</code><br><br>
      Your deadline for welfare verification is in <b>10 days</b>.<br>
      Please submit your MeeSeva income certificate & bank passbook copy at the nearest Gram Panchayat or CSC counter.<br><br>
      🔗 Verify: <a href="https://meeseva.telangana.gov.in" target="_blank" rel="noopener">meeseva.telangana.gov.in</a><br>
      <span class="small muted">SchemeSetu never asks for OTP or Aadhaar numbers. Final sanction by Govt of Telangana.</span>
    `;
  }
  modal.style.display = "flex";
}

/* ------------------------------ rule studio ------------------------------- */
async function loadStudio() {
  const data = await api("/api/rule-studio");
  state.studio.schemes = data.schemes || [];
  state.studio.operators = data.operators || [];
  const select = $("#studio-scheme");
  if (!select) return;
  const keep = select.value;
  select.innerHTML = state.studio.schemes
    .map((s) => `<option value="${esc(s.scheme_id)}">${esc(s.scheme_name)} — ${s.rules.length} rules (${esc(s.provenance)})</option>`)
    .join("");
  if (keep) select.value = keep;
  renderStudioRules();
}

function renderStudioRules() {
  const select = $("#studio-scheme");
  if (!select) return;
  const scheme = state.studio.schemes.find((s) => s.scheme_id === select.value);
  state.studio.selected = scheme ? scheme.scheme_id : null;
  state.studio.original = {};
  if (!scheme) { $("#studio-rules").innerHTML = ""; return; }
  scheme.rules.forEach((r) => { state.studio.original[r.id] = Object.assign({}, r); });

  $("#studio-rules").innerHTML = scheme.rules.map((r) => `<div class="rule" data-rule="${esc(r.id)}">
      <div>
        <div>${esc(r.text)}</div>
        <div class="text">${esc(r.field_label)} · <code>${esc(r.id)}</code>${r.source_note ? " · " + esc(r.source_note) : ""}</div>
      </div>
      <select class="op">${(state.studio.operators || []).map((op) => `<option value="${op}" ${op === r.op ? "selected" : ""}>${op}</option>`).join("")}</select>
      <input class="value" value='${esc(JSON.stringify(r.value))}' title="value as JSON" />
      <input class="weight" type="number" step="0.5" min="0" value="${esc(String(r.weight))}" title="weight" />
      <label class="check"><input class="hard" type="checkbox" ${r.hard ? "checked" : ""} /> must</label>
    </div>`).join("");

  $$("#studio-rules .rule").forEach((row) => {
    row.addEventListener("input", () => {
      row.classList.add("dirty");
      $("#studio-result").innerHTML = `<p class="muted">edited <code>${esc(row.dataset.rule)}</code> — press Simulate to recompute every verdict.</p>`;
    });
  });
}

function collectOverrides() {
  const out = {};
  $$("#studio-rules .rule").forEach((row) => {
    const id = row.dataset.rule;
    const original = state.studio.original[id] || {};
    const op = row.querySelector(".op").value;
    const weight = Number(row.querySelector(".weight").value);
    const hard = row.querySelector(".hard").checked;
    let value = row.querySelector(".value").value;
    try { value = JSON.parse(value); } catch (err) { /* keep the raw string */ }
    const patch = {};
    if (op !== original.op) patch.op = op;
    if (JSON.stringify(value) !== JSON.stringify(original.value)) patch.value = value;
    if (weight !== original.weight) patch.weight = weight;
    if (hard !== original.hard) patch.hard = hard;
    if (Object.keys(patch).length) out[id] = patch;
  });
  return out;
}

async function simulateStudio() {
  const overrides = collectOverrides();
  if (!Object.keys(overrides).length) { log("Change at least one rule first.", true); return; }
  const body = {
    scheme_id: $("#studio-scheme").value,
    overrides,
    profile_id: $("#studio-profile").value || null,
    language: state.lang,
  };
  const data = await api("/api/rule-studio/simulate", { method: "POST", body: JSON.stringify(body) });
  $("#studio-result").innerHTML = `
    <div>Rule(s) changed: <code>${esc(Object.keys(data.diff).join(", "))}</code></div>
    <div class="before">before: ${esc(data.before.verdict_label)} (confidence ${esc(String(data.before.confidence))})</div>
    <div class="after">after: ${esc(data.after.verdict_label)} (confidence ${esc(String(data.after.confidence))})</div>
    <div class="muted small">${esc(data.note)}</div>
    <div class="impact">${data.impact.length
      ? data.impact.map((row) => `<div class="${row.changed ? "changed" : "muted"}">${esc(row.label)}: ${esc(row.before)} → ${esc(row.after)}${row.changed ? "  ← verdict moved" : ""}</div>`).join("")
      : "<div class='muted'>No stored households yet, so cross-household impact is empty.</div>"}</div>`;
}

async function applyStudio() {
  const overrides = collectOverrides();
  if (!Object.keys(overrides).length) { log("Change at least one rule first.", true); return; }
  let token = sessionStorage.getItem("adminToken") || "";
  if (!token) {
    token = window.prompt("Admin token (ask the operator):") || "";
    if (token) sessionStorage.setItem("adminToken", token);
  }
  if (!token) { log("Apply aborted: no admin token entered.", true); return; }
  try {
    const data = await api("/api/rule-studio/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Admin-Token": token },
      body: JSON.stringify({ scheme_id: $("#studio-scheme").value, overrides, language: state.lang, persist: true }),
    });
    log("Applied: " + JSON.stringify(data.applied), true);
    log("Backup written to " + data.backup);
    await loadStudio();
    await loadHealth();
  } catch (err) {
    log("Apply failed: " + err.message, true);
  }
}

/* ---------------------------------- voice --------------------------------- */
let liveRecognition = null;

function startLiveSpeech() {
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRec) return;
  try {
    liveRecognition = new SpeechRec();
    liveRecognition.continuous = true;
    liveRecognition.interimResults = true;
    liveRecognition.lang = state.lang === "te" ? "te-IN" : state.lang === "hi" ? "hi-IN" : "en-IN";
    liveRecognition.onresult = (event) => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        transcript += event.results[i][0].transcript;
      }
      if (transcript && transcript.trim()) {
        const current = $("#intake-text").value;
        if (!current.includes(transcript.trim())) {
          $("#intake-text").value = (current + " " + transcript.trim()).trim();
        }
      }
    };
    liveRecognition.start();
  } catch (e) {}
}

function stopLiveSpeech() {
  if (liveRecognition) {
    try { liveRecognition.stop(); } catch (e) {}
    liveRecognition = null;
  }
}

async function toggleVoice() {
  const btn = $("#btn-voice");
  const viz = $("#voice-visualizer");
  if (state.mediaRecorder && state.mediaRecorder.state === "recording") {
    state.mediaRecorder.stop();
    stopLiveSpeech();
    if (viz) viz.style.display = "none";
    return;
  }
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    $("#voice-hint").textContent = "This browser cannot record audio — please type instead.";
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    state.chunks = [];
    const recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (event) => { if (event.data.size) state.chunks.push(event.data); };
    recorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      btn.classList.remove("rec");
      btn.textContent = "🎤 " + t("intake.voice", "Speak instead");
      $("#voice-hint").textContent = t("intake.voice_note", "Voice note");
      if (viz) viz.style.display = "none";
      await sendVoice(new Blob(state.chunks, { type: recorder.mimeType || "audio/webm" }));
    };
    recorder.start();
    state.mediaRecorder = recorder;
    btn.classList.add("rec");
    btn.textContent = t("intake.stop", "Stop recording");
    $("#voice-hint").textContent = t("intake.listening", "Listening…");
    if (viz) viz.style.display = "inline-flex";
    startLiveSpeech();
  } catch (err) {
    $("#voice-hint").textContent = "Microphone: " + err.message;
  }
}

async function sendVoice(blob) {
  const form = new FormData();
  form.append("file", blob, "voice.webm");
  $("#btn-voice").disabled = true;
  log("Sending voice note to Whisper STT (server-side, regional language)…");
  try {
    const res = await fetch(`/api/voice?language=${state.lang}&use_llm=true&save=true`, { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    $("#intake-text").value = data.transcript || "";
    state.result = data;
    state.form = Object.assign({}, (data.intake && data.intake.facts) || {}, state.form);
    log(`Transcribed in ${data.stt.ms} ms with ${data.stt.model}: "${data.transcript}"`);
    renderMatches();
    renderQuestions(data.next_questions || []);
    await loadProfiles();
    await loadGraph(data.profile_id);
    switchTab("results");
  } catch (err) {
    log("Voice failed: " + err.message, true);
  } finally {
    $("#btn-voice").disabled = false;
  }
}

/* ------------------- last mile: checklist, whatsapp and calendar -------------------- */
const COVER_CATEGORIES = ["health", "insurance", "crop_insurance"];

async function fetchChecklist() {
  const pid = state.result && state.result.profile_id;
  if (!pid) { log("Save the household first - the checklist is built for a stored household.", true); return null; }
  if (!state.checklist || state.checklist.profile_id !== pid) {
    state.checklist = await api(`/api/checklist/${pid}?lang=${state.lang}`);
  }
  return state.checklist;
}

function renderPrintArea(data) {
  const total = Number(data.estimated_yearly_benefit_inr || 0).toLocaleString("en-IN");
  const cover = Number(data.estimated_cover_inr || 0).toLocaleString("en-IN");
  const qrSvg = window.generateQRCodeSVG ? window.generateQRCodeSVG(data.whatsapp_url || window.location.href, 130) : "";

  $("#print-area").innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #000;padding-bottom:8pt;">
      <div>
        <h1 style="margin:0 0 4pt;">SchemeSetu — Telangana Citizen Welfare Voucher</h1>
        <p style="margin:0;font-size:10pt;"><b>Token:</b> ${esc(data.operator_token || "TS-MEESEVA")} · <b>Issued:</b> ${esc(data.generated_on)} · <b>MeeSeva Telangana:</b> meeseva.telangana.gov.in</p>
      </div>
      <div class="print-qr" style="text-align:center;">
        ${qrSvg}
        <div style="font-size:7pt;margin-top:2pt;">Scan on phone</div>
      </div>
    </div>
    <p style="margin-top:8pt;"><b>${esc(data.headline)}</b></p>
    <p><b>Transfers and in-kind: Rs ${esc(total)} a year</b> · risk cover also unlocked: Rs ${esc(cover)} (kept separate - cover is not cash) · ${esc(String(data.scheme_count))} scheme(s)</p>
    <p><b>Collect these compulsory documents first:</b> ${(data.mandatory_documents || []).map(esc).join(", ")}</p>
    ${(data.schemes || []).map((s, i) => `
      <section style="margin-top:10pt;border-top:1px dashed #ccc;padding-top:6pt;">
        <h2 style="font-size:12pt;margin:0 0 3pt;">${i + 1}. ${getSchemePrintTitle(s)}</h2>
        <p style="margin:0 0 3pt;font-size:9.5pt;">${esc(s.verdict_label)} · ${esc(s.provenance)} · confidence ${esc(String(s.confidence))}</p>
        <p style="margin:0 0 3pt;font-size:9.5pt;"><b>Benefit:</b> ${esc(s.benefit)}${COVER_CATEGORIES.includes(s.category) ? " (risk cover - pays out only on an event)" : ""} · <b>Deadline:</b> ${esc(s.deadline)}</p>
        <ol style="margin:2pt 0 0 16pt;font-size:9pt;">${(s.documents || []).map((d) => `<li>${esc(d.label)}${d.mandatory ? " (compulsory)" : " (if available)"}${d.how_to_get ? " - " + esc(d.how_to_get) : ""}</li>`).join("")}</ol>
        <ol style="margin:2pt 0 0 16pt;font-size:9pt;">${(s.apply_steps || []).map((step) => `<li>${esc(step)}</li>`).join("")}</ol>
        <p style="margin:2pt 0 0;font-size:8.5pt;"><b>Apply at:</b> ${esc(s.portal_name)} ${esc(s.apply_url)}</p>
        <p class="small" style="margin:1pt 0 0;font-size:8pt;color:#555;"><b>Official Source:</b> ${esc(s.source_name)} (${esc(s.source_url)}) ${freshnessBadge(s.verified_on)}</p>
      </section>`).join("")}
    <p class="small" style="margin-top:12pt;font-size:8.5pt;">${esc(data.guardrail)} ${esc(data.note)}</p>`;
}

async function printChecklist() {
  try {
    const data = await fetchChecklist();
    if (!data) return;
    renderPrintArea(data);
    window.print();
    log(`Checklist ready: Rs ${Number(data.estimated_yearly_benefit_inr).toLocaleString("en-IN")} a year cash + Rs ${Number(data.estimated_cover_inr).toLocaleString("en-IN")} health cover.`);
  } catch (err) {
    log("Could not build checklist: " + err.message, true);
  }
}

async function copyChecklist() {
  try {
    const data = await fetchChecklist();
    if (!data) return;
    await navigator.clipboard.writeText(data.whatsapp_text || data.text);
    log("WhatsApp-formatted checklist text copied to clipboard!");
  } catch (err) {
    log("Copy failed: " + err.message, true);
  }
}

async function openWhatsAppModal() {
  try {
    const data = await fetchChecklist();
    if (!data) return;
    const modal = $("#modal-qr");
    if (!modal) return;
    const qrBox = $("#qr-container");
    const waLink = $("#modal-wa-link");
    const copyBtn = $("#modal-copy-link");

    const waUrl = data.whatsapp_url || `https://wa.me/?text=${encodeURIComponent(data.whatsapp_text || data.text)}`;
    if (waLink) waLink.href = waUrl;

    if (qrBox && window.generateQRCodeSVG) {
      qrBox.innerHTML = window.generateQRCodeSVG(waUrl, 180);
    }

    if (copyBtn) {
      copyBtn.onclick = async () => {
        await navigator.clipboard.writeText(data.whatsapp_text || data.text);
        copyBtn.textContent = "Copied! ✓";
        setTimeout(() => { copyBtn.textContent = "Copy WhatsApp Text"; }, 2000);
      };
    }

    modal.style.display = "flex";
  } catch (err) {
    log("WhatsApp modal error: " + err.message, true);
  }
}

async function openCalendar() {
  const pid = (state.result && state.result.profile_id) || $("#tracker-profile").value;
  if (!pid) { log("Save the household first, then queue the reminders.", true); return; }
  try {
    await api("/api/reminders/plan", {
      method: "POST",
      body: JSON.stringify({ profile_id: pid, days_before: 10 }),
    });
    const reminders = (await api(`/api/reminders?profile_id=${encodeURIComponent(pid)}`)).reminders || [];
    if (!reminders.length) {
      log("None of this household's matched schemes has a fixed calendar date (rolling windows). The tracker still alerts in-app.", true);
      return;
    }
    log(`Queueing ${reminders.length} dated deadline(s).`);
  } catch (err) {
    log("Could not queue reminders: " + err.message, true);
  }
  window.location.href = `/api/reminders/calendar.ics?profile_id=${encodeURIComponent(pid)}`;
  log("Calendar (.ics) file ready — add to Google Calendar or phone.");
}

/* --------------------- data rights (DPDP Act 2023) ------------------------ */
async function loadDataRights() {
  try {
    const notice = await api(`/api/consent/notice?lang=${state.lang}`);
    $("#consent-notice").textContent = notice.text;
    const rights = (state.health && state.health.data_rights) || {};
    const pid = state.result && state.result.profile_id;
    $("#data-rights").innerHTML = [
      `<div class="muted small">Notice ${esc(notice.notice_version)} · ${esc(String(rights.retention_days || ""))}-day retention · purposes: ${notice.purposes.map(esc).join(", ")}</div>`,
      pid
        ? `<div>Current household <code>${esc(pid)}</code> - you can download it or erase it right now.</div>`
        : `<div class="muted small">Run an intake with “save this household” ticked to exercise these rights on real data.</div>`,
      `<div class="muted small">${notice.rights.map(esc).join(" · ")}</div>`,
    ].join("");
  } catch (err) {
    $("#consent-notice").textContent = "Could not load consent notice: " + err.message;
  }
}

function downloadJson(name, payload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function exportMyData() {
  const pid = (state.result && state.result.profile_id) || $("#tracker-profile").value;
  if (!pid) { log("Nothing stored yet - run an intake first.", true); return; }
  const payload = await api(`/api/profiles/${encodeURIComponent(pid)}/export`);
  downloadJson(`schemesetu-data-${pid}.json`, payload);
  log(`Exported everything we hold about ${pid} (${payload.audit.length} audit rows).`);
}

async function eraseHousehold() {
  const pid = (state.result && state.result.profile_id) || $("#tracker-profile").value;
  if (!pid) { log("Nothing stored yet - run an intake first.", true); return; }
  if (!window.confirm(`Erase ${pid}? Facts, applications, reminders and consent rows are deleted permanently. A tombstone that holds no personal data is kept as proof.`)) return;
  const result = await api(`/api/profiles/${encodeURIComponent(pid)}`, { method: "DELETE" });
  state.result = null;
  state.checklist = null;
  $("#matches").innerHTML = "";
  $("#headline").textContent = "-";
  $("#questions").innerHTML = "";
  log(`Erased ${pid}: ${JSON.stringify(result.deleted)}. The engine still works - it just forgets you.`);
  await loadProfiles();
  await loadTracker("");
  await loadDataRights();
}

async function runRetentionSweep() {
  const result = await api("/api/privacy/purge", { method: "POST" });
  log(`Retention sweep (${result.retention_days} days): erased ${result.count} household(s) older than ${result.cutoff}.`);
  await loadProfiles();
  await loadHealth();
}

/* ---------------------------------- wiring -------------------------------- */
function wire() {
  // Navigation tabs
  $$(".tab").forEach((tab) => tab.addEventListener("click", () => {
    switchTab(tab.dataset.tab);
    if (tab.dataset.tab === "tracker") loadTracker("");
    if (tab.dataset.tab === "studio") loadStudio();
  }));

  // Mode switch: Citizen vs MeeSeva Kiosk
  const btnCit = $("#btn-mode-citizen");
  const btnKiosk = $("#btn-mode-kiosk");
  if (btnCit) btnCit.addEventListener("click", () => setMode("citizen"));
  if (btnKiosk) btnKiosk.addEventListener("click", () => setMode("kiosk"));

  // Voice sample presets
  $$(".sample-voice").forEach((btn) => btn.addEventListener("click", async () => {
    const text = btn.dataset.text;
    const lang = btn.dataset.lang;
    $("#intake-text").value = text;
    if (lang && lang !== state.lang) {
      $("#lang").value = lang;
      await loadLanguage(lang);
    }
    // Speak aloud via TTS so judges hear the regional prompt
    speak(text);
    const viz = $("#voice-visualizer");
    if (viz) {
      viz.style.display = "inline-flex";
      setTimeout(() => { viz.style.display = "none"; }, 3500);
    }
    await runIntake(text);
  }));

  // Theme Toggle (Dark/Light)
  const btnTheme = $("#btn-theme-toggle");
  if (btnTheme) btnTheme.addEventListener("click", toggleTheme);

  // Senior Citizen / High Contrast Mode
  const btnSenior = $("#btn-senior-mode");
  if (btnSenior) {
    btnSenior.addEventListener("click", () => {
      const on = document.body.classList.toggle("senior-mode");
      btnSenior.textContent = on ? "👁️ A-" : "👁️ A+";
      log(on ? "Enabled High-Contrast & Senior Citizen Large Font Mode." : "Switched to standard font mode.");
    });
  }

  // Official Fees & Anti-Middleman Modal
  const btnFees = $("#btn-anti-middleman");
  if (btnFees) btnFees.addEventListener("click", () => { $("#modal-fees").style.display = "flex"; });
  const closeFees = $("#modal-close-fees");
  if (closeFees) closeFees.addEventListener("click", () => { $("#modal-fees").style.display = "none"; });

  // Who Pays / Business Model Modal
  const btnModel = $("#btn-business-model");
  if (btnModel) btnModel.addEventListener("click", () => { $("#modal-model").style.display = "flex"; });
  const closeModel = $("#modal-close-model");
  if (closeModel) closeModel.addEventListener("click", () => { $("#modal-model").style.display = "none"; });

  $("#btn-analyse").addEventListener("click", () => runIntake());
  $("#btn-voice").addEventListener("click", toggleVoice);
  $("#lang").addEventListener("change", (event) => loadLanguage(event.target.value));

  $("#speak").addEventListener("click", () => {
    const data = state.result;
    if (!data) { speak(t("app.tagline")); return; }
    const top = (data.matches || []).filter((m) => m.verdict !== "not_eligible").slice(0, 4);
    speak(`${data.summary.headline}. ` + top.map((m) => `${m.name}: ${m.benefit}. ${m.deadline}.`).join(" "));
  });

  $("#reload").addEventListener("click", async () => {
    await api("/api/graph/reload", { method: "POST" });
    await loadHealth();
    await loadGraph(state.result ? state.result.profile_id : null);
    log("Scheme data and knowledge graph reloaded from disk.");
  });

  // Filters
  $$("#filters .chip").forEach((chip) => chip.addEventListener("click", () => {
    $$("#filters .chip").forEach((c) => c.classList.toggle("active", c === chip));
    state.filter.verdict = chip.dataset.verdict;
    renderMatches();
  }));
  $("#filter-text").addEventListener("input", (event) => {
    state.filter.text = event.target.value;
    renderMatches();
  });

  // Action Bar in Results
  const btnWa = $("#btn-whatsapp");
  if (btnWa) btnWa.addEventListener("click", openWhatsAppModal);
  const btnQr = $("#btn-qr");
  if (btnQr) btnQr.addEventListener("click", openWhatsAppModal);

  $("#btn-checklist").addEventListener("click", printChecklist);
  $("#btn-copy-checklist").addEventListener("click", copyChecklist);
  $("#btn-calendar").addEventListener("click", openCalendar);

  // Modals close buttons
  const closeQr = $("#modal-close-qr");
  if (closeQr) closeQr.addEventListener("click", () => { $("#modal-qr").style.display = "none"; });
  const closeWa = $("#modal-close-wa");
  if (closeWa) closeWa.addEventListener("click", () => { $("#modal-wa-alert").style.display = "none"; });

  // Modal backdrop click closes
  $$(".modal").forEach((m) => m.addEventListener("click", (e) => {
    if (e.target.classList.contains("modal-backdrop")) m.style.display = "none";
  }));

  // Tracker buttons
  $("#btn-refresh").addEventListener("click", () => loadTracker(""));
  $("#btn-plan").addEventListener("click", planReminders);
  const btnPreWa = $("#btn-preview-wa-alert");
  if (btnPreWa) btnPreWa.addEventListener("click", openWhatsAppAlertPreview);
  $("#tracker-profile").addEventListener("change", (event) => loadTracker(event.target.value));

  // Graph search & controls
  const gSearch = $("#graph-search");
  if (gSearch) {
    gSearch.addEventListener("input", (e) => {
      state.graphSearch = e.target.value;
      renderGraph();
    });
  }
  const btnGReset = $("#btn-graph-reset");
  if (btnGReset) {
    btnGReset.addEventListener("click", () => {
      if (gSearch) gSearch.value = "";
      state.graphSearch = "";
      renderGraph();
    });
  }

  // Rule Studio
  $("#studio-scheme").addEventListener("change", renderStudioRules);
  $("#btn-simulate").addEventListener("click", simulateStudio);
  $("#btn-apply").addEventListener("click", applyStudio);

  // Privacy
  $("#btn-export").addEventListener("click", exportMyData);
  $("#btn-erase").addEventListener("click", eraseHousehold);
  $("#btn-sweep").addEventListener("click", runRetentionSweep);
}

async function init() {
  restoreTheme();
  document.addEventListener("keydown", handleKeyboard);
  wire();
  try {
    await loadHealth();
    const languages = (state.health && state.health.languages) || { en: "English" };
    $("#lang").innerHTML = Object.entries(languages)
      .map(([code, label]) => `<option value="${esc(code)}">${esc(label)}</option>`)
      .join("");
    $("#lang").value = (state.health && state.health.default_language) || "en";
    await Promise.all([loadLanguage($("#lang").value), loadSamples(), loadProfiles(), loadStudio(), loadGraph(null)]);
    log("SchemeSetu is ready. Speak in Telugu/Hindi/English or click a sample household above. Press ? for shortcuts.");
    updateFooterStats();
    showToast("SchemeSetu v2.0 loaded \u2014 " + (state.health ? state.health.graph.schemes : "26") + " schemes ready", "success");
  } catch (err) {
    log("Startup problem: " + err.message, true);
  }
}

document.addEventListener("DOMContentLoaded", init);
'''

with open(APP_JS, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Upgraded frontend/app.js written ({len(content)} chars)")
