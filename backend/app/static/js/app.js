/* Shared helpers + page shell (sidebar, header). Every page calls initPage(...). */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function esc(v) {
  return String(v == null ? "" : v).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function errText(data, status) {
  if (data && typeof data.detail === "string") return data.detail;
  if (data && Array.isArray(data.detail)) return data.detail.map(d => d.msg).join("; ");
  return "Request failed (" + status + ")";
}

async function api(path, options = {}) {
  const opts = Object.assign({ credentials: "same-origin" }, options);
  opts.headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
  if (opts.body && typeof opts.body !== "string") opts.body = JSON.stringify(opts.body);
  let res;
  try { res = await fetch(path, opts); }
  catch (e) { throw new Error("Cannot reach the server. Is it still running?"); }
  if (res.status === 401 && !location.pathname.startsWith("/login")) {
    location.href = "/login";
    throw new Error("Please log in again.");
  }
  let data = null;
  try { data = await res.json(); } catch (e) { /* no body */ }
  if (!res.ok) { const err = new Error(errText(data, res.status)); err.code = data && data.code; throw err; }
  return data;
}
const post = (path, body) => api(path, { method: "POST", body: body || {} });

function toast(msg, type = "info") {
  let box = $("#toasts");
  if (!box) { box = document.createElement("div"); box.id = "toasts"; document.body.appendChild(box); }
  const t = document.createElement("div");
  t.className = "toast " + type;
  t.textContent = msg;
  box.appendChild(t);
  setTimeout(() => t.remove(), 4500);
}

function confirmDialog(message, okLabel = "Confirm") {
  return new Promise(resolve => {
    const d = document.createElement("dialog");
    d.innerHTML = `<p style="margin-top:0">${esc(message)}</p><div class="actions" style="justify-content:flex-end">
      <button class="btn" data-v="0">Cancel</button><button class="btn primary" data-v="1">${esc(okLabel)}</button></div>`;
    d.addEventListener("click", e => {
      const v = e.target.getAttribute && e.target.getAttribute("data-v");
      if (v !== null && v !== undefined) { d.close(); d.remove(); resolve(v === "1"); }
    });
    d.addEventListener("cancel", () => { d.remove(); resolve(false); });
    document.body.appendChild(d);
    d.showModal();
  });
}

/* run an action button: confirm (optional) -> call -> toast -> reload */
async function runAction(fn, okMsg, reload) {
  try { const r = await fn(); if (okMsg) toast(okMsg, "success"); if (reload) await reload(); return r; }
  catch (e) { toast(e.message, "error"); if (reload) { try { await reload(); } catch (x) { /* ignore */ } } }
}

const badge = (value) => value ? `<span class="badge b-${esc(String(value).toLowerCase())}">${esc(String(value).replace(/_/g, " "))}</span>` : '<span class="muted">-</span>';
const timeOnly = (s) => s ? String(s).slice(11, 19) : "-";
const dash = (v, suffix = "") => (v === null || v === undefined || v === "") ? "-" : esc(v) + suffix;

function animateCount(el, to) {
  const from = parseInt(el.dataset.v || "0", 10);
  el.dataset.v = to;
  if (from === to) { el.textContent = to; return; }
  const start = performance.now();
  (function tick(t) {
    const p = Math.min(1, (t - start) / 500);
    el.textContent = Math.round(from + (to - from) * p);
    if (p < 1) requestAnimationFrame(tick);
  })(start);
}

function skeleton(n = 4) { return Array.from({ length: n }, () => '<div class="skel"></div>').join(""); }
function emptyState(text) { return `<div class="empty">${esc(text)}</div>`; }
function table(headers, rows, rowAttr) {
  if (!rows.length) return "";
  return `<div class="tablewrap"><table><thead><tr>${headers.map(h => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${
    rows.map((r, i) => `<tr ${rowAttr ? rowAttr(i) : ""}>${r.map(c => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

const NAV = [
  ["dashboard", "/dashboard", "🏠", "Dashboard"], ["capacity", "/capacity", "🛏️", "Capacity"],
  ["emergencies", "/emergencies", "🚨", "Emergencies"], ["patients", "/patients", "🧑‍⚕️", "Patients"],
  ["ambulance", "/ambulance", "🚑", "Ambulance"], ["alerts", "/alerts", "🔔", "Alerts"],
  ["integration-log", "/integration-log", "📤", "Integration"], ["profile", "/profile", "👤", "Profile"],
];

async function updateBadge() {
  try {
    const d = await api("/api/alerts?unread=true");
    const el = $("#alertCount");
    if (el) { el.textContent = d.unread; el.hidden = !d.unread; }
  } catch (e) { /* ignore */ }
}

async function initPage(page, title, onReady) {
  const content = $("#page");
  let me;
  try { me = await api("/api/auth/me"); } catch (e) { return; }
  window.ME = me;
  const shell = $("#shell");
  shell.className = "shell";
  shell.innerHTML = `
    <aside class="sidebar" id="sidebar">
      <div class="brand"><b>🏥 Hospital Module</b><span>Emergency Control Room</span></div>
      <nav class="nav">
        ${NAV.map(n => `<a href="${n[1]}" class="${n[0] === page ? "active" : ""}"><span>${n[2]}</span>${n[3]}${n[0] === "alerts" ? '<span class="count" id="alertCount" hidden>0</span>' : ""}</a>`).join("")}
        <a href="#" id="logout" class="logout"><span>🚪</span>Logout</a>
      </nav>
    </aside>
    <div class="main">
      <header class="topbar">
        <button class="menu-btn" id="menuBtn" aria-label="Menu">☰</button>
        <div><div class="hname">${esc(me.hospital.name)}</div><div class="muted small">${esc(me.hospital.id)} · ${esc(me.user.username)}</div></div>
        <span id="hStatus">${badge(me.hospital.status)}</span>
        <span class="sp"></span>
        <span class="tag">DEMO DATA</span>
        ${me.config.mock_control_room ? '<span class="tag mock">MOCK CONTROL ROOM</span>' : '<span class="tag mock">LIVE CONTROL ROOM</span>'}
        <span class="muted small" id="clock"></span>
      </header>
      <main id="content"></main>
    </div>`;
  $("#content").appendChild(content);
  content.hidden = false;
  document.title = title + " · Hospital Module";
  $("#menuBtn").onclick = () => $("#sidebar").classList.toggle("open");
  $("#logout").onclick = async (e) => { e.preventDefault(); await post("/api/auth/logout").catch(() => {}); location.href = "/login"; };
  const tick = () => { $("#clock").textContent = new Date().toLocaleTimeString(); };
  tick(); setInterval(tick, 1000);
  updateBadge(); setInterval(updateBadge, 8000);
  await onReady(me);
}

function setHeaderStatus(status) { const el = $("#hStatus"); if (el) el.innerHTML = badge(status); }

/* poll helper that does not stack requests */
function poll(fn, ms) {
  let busy = false;
  const run = async () => { if (busy || document.hidden) return; busy = true; try { await fn(); } catch (e) { /* shown by caller */ } busy = false; };
  run(); return setInterval(run, ms);
}

/* ---- mock control room button helper (used on several pages) ---- */
async function sendSample(bedType, reload) {
  const r = await post("/api/integration/mock/sample-emergency", { bed_type: bedType, severity: "CRITICAL" });
  const id = r.emergency.emergency_id;
  if (r.result === "ACCEPTED") toast(`${id} accepted - ${bedType} bed reserved`, "success");
  else if (r.result.startsWith("REJECTED")) toast(`${id}: NO SUITABLE ${bedType} BED - reported to Control Room`, "error");
  else toast(`${id} received (${r.result})`);
  if (reload) await reload();
  return r;
}

function askText(message, value = "") {
  return new Promise(resolve => {
    const d = document.createElement("dialog");
    d.innerHTML = `<p style="margin-top:0">${esc(message)}</p><input id="askInput" value="${esc(value)}" maxlength="100">
      <div class="actions" style="justify-content:flex-end;margin-top:14px"><button class="btn" data-v="0">Cancel</button><button class="btn primary" data-v="1">OK</button></div>`;
    d.addEventListener("click", e => {
      const v = e.target.getAttribute && e.target.getAttribute("data-v");
      if (v === "0" || v === "1") { const val = $("#askInput", d).value.trim(); d.close(); d.remove(); resolve(v === "1" && val ? val : null); }
    });
    d.addEventListener("cancel", () => { d.remove(); resolve(null); });
    document.body.appendChild(d); d.showModal();
  });
}

/* ---- emergency table shared by Dashboard + Emergencies ---- */
function emergencyTable(items) {
  return table(["Emergency ID", "Patient ID", "Type", "Severity", "Ambulance", "ETA", "Required Bed", "Status", "Action"],
    items.map(e => [
      `<b>${esc(e.emergency_id)}</b>`, esc(e.patient_id), esc(e.emergency_type), badge(e.severity),
      e.ambulance_id ? `${esc(e.ambulance_id)} ${badge(e.ambulance_status)}` : "-",
      e.ambulance_id ? (e.ambulance_status === "ARRIVED" ? "Arrived" : dash(e.eta_minutes, " min")) : "-",
      esc(e.required_bed_type), badge(e.status),
      `<div class="actions"><a class="btn sm" href="/emergency-details?id=${encodeURIComponent(e.emergency_id)}">View</a>${
        e.status === "INCOMING" ? `<button class="btn sm primary" data-act="accept" data-id="${esc(e.emergency_id)}">Accept</button><button class="btn sm danger" data-act="reject" data-id="${esc(e.emergency_id)}">Reject</button>` : ""}</div>`]));
}

function bindEmergencyActions(root, reload) {
  root.addEventListener("click", async ev => {
    const b = ev.target.closest("button[data-act]");
    if (!b) return;
    const id = b.dataset.id;
    if (b.dataset.act === "accept") {
      runAction(() => post(`/api/emergencies/${encodeURIComponent(id)}/accept`), `${id} accepted - bed reserved`, reload);
    } else if (b.dataset.act === "reject") {
      if (!await confirmDialog(`Reject emergency ${id}? The Control Room will be told to redirect it.`, "Reject")) return;
      runAction(() => post(`/api/emergencies/${encodeURIComponent(id)}/reject`, { reason: "Rejected by hospital staff" }), `${id} rejected`, reload);
    }
  });
}

/* ---- new-emergency indicator: toast when an unseen emergency id appears ---- */
let _knownEmergencies = null;
function watchNewEmergencies(items) {
  const ids = new Set(items.map(e => e.emergency_id));
  if (_knownEmergencies) {
    items.forEach(e => { if (!_knownEmergencies.has(e.emergency_id)) toast(`🚨 New emergency ${e.emergency_id} (${e.severity})`, "error"); });
  }
  _knownEmergencies = ids;
}

function capacityBar(c) {
  const o = c.total ? c.occupied * 100 / c.total : 0, r = c.total ? c.reserved * 100 / c.total : 0;
  return `<div class="bar"><i class="o" style="width:${o}%"></i><i class="r" style="width:${r}%"></i></div>
    <div class="legend"><span>Total <b>${c.total}</b></span><span>Occupied <b>${c.occupied}</b></span><span>Reserved <b>${c.reserved}</b></span><span>Free <b>${c.free}</b></span></div>`;
}
