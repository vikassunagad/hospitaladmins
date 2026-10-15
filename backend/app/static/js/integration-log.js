async function load() {
  const dir = $("#dirFilter").value;
  const d = await api("/api/integration/reports" + (dir ? "?direction=" + dir : ""));
  $("#modeInfo").textContent = d.mock_mode ? "Mock mode: outgoing reports are stored here instead of being sent over the network." : "Live mode: reports are POSTed to the Control Room.";
  $("#logTable").innerHTML = d.items.length ? table(["Time", "Direction", "Event", "Emergency ID", "Status", "Details"],
    d.items.map(r => [esc(timeOnly(r.time)), `<span class="badge ${r.direction === "IN" ? "b-info" : "b-warning"}">${esc(r.direction)}</span>`, `<b>${esc(r.event)}</b>`,
      esc(r.emergency_id || "-"), badge(r.status === "RECEIVED" ? "OK" : r.status), `<details><summary class="small">view</summary><pre class="small" style="white-space:pre-wrap;max-width:420px">${esc(r.error || r.payload || "")}</pre></details>`])) : emptyState("No messages yet.");
}
initPage("integration-log", "Integration Log", async () => {
  $("#logTable").innerHTML = skeleton(6);
  $("#dirFilter").onchange = load;
  poll(async () => { try { await load(); } catch (e) { $("#logTable").innerHTML = `<div class="errorbox">${esc(e.message)}</div>`; } }, 4000);
});
