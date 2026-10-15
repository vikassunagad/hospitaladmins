const TYPES = ["GENERAL", "ICU", "EMERGENCY"];
const TITLES = { GENERAL: "General beds", ICU: "ICU beds", EMERGENCY: "Emergency beds" };

async function load() {
  if (document.activeElement && document.activeElement.tagName === "INPUT") return;   // do not disturb typing
  const d = await api("/api/capacity");
  setHeaderStatus(d.status);
  $("#capStatus").innerHTML = badge(d.status);
  $("#capGrid").innerHTML = `<section class="card capacity-panel"><h2>Beds by type</h2><div class="capacity-types">${TYPES.map(t => {
    const c = d.capacity[t];
    return `<article class="capacity-type"><h3>${TITLES[t]}<span class="sp"></span><span class="badge ${c.free === 0 ? "b-critical" : "b-normal"}">${c.free} free</span></h3>
      ${capacityBar(c)}
      <div class="row" style="margin-top:14px">
        <div><label>Total</label><input type="number" min="0" id="tot-${t}" value="${c.total}"></div>
        <div><label>Occupied</label><input type="number" min="0" id="occ-${t}" value="${c.occupied}"></div>
        <div style="flex:0"><button class="btn primary" data-save="${t}">Save</button></div>
      </div>
      <p class="muted small" style="margin-bottom:0">Reserved (${c.reserved}) is protected for incoming emergencies and cannot be edited here.</p></article>`;
  }).join("")}</div></section>`;
  $("#capThresholds").textContent = `HIGH LOAD at ${d.thresholds.high_load}% · CRITICAL at ${d.thresholds.critical}% (configurable in .env)`;
  $("#capUpdated").textContent = "Last updated " + new Date().toLocaleTimeString();
}

initPage("capacity", "Capacity", async () => {
  $("#capGrid").innerHTML = skeleton(5);
  $("#capGrid").addEventListener("click", async (ev) => {
    const b = ev.target.closest("button[data-save]");
    if (!b) return;
    const t = b.dataset.save;
    const total = parseInt($("#tot-" + t).value, 10), occupied = parseInt($("#occ-" + t).value, 10);
    if (Number.isNaN(total) || Number.isNaN(occupied)) return toast("Enter valid numbers.", "error");
    if (!await confirmDialog(`Update ${TITLES[t]}: total ${total}, occupied ${occupied}?`, "Update")) return;
    document.activeElement.blur();
    await runAction(() => api("/api/capacity", { method: "PUT", body: { bed_type: t, total, occupied } }), "Capacity updated and reported to Control Room", load);
  });
  poll(async () => { try { await load(); } catch (e) { $("#capGrid").innerHTML = `<div class="errorbox">${esc(e.message)}</div>`; } }, 6000);
});
