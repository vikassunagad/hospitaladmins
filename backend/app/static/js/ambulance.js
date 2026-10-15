let tracker = null, current = null;

async function selectEmergency(eid) {
  const d = await api("/api/emergencies/" + encodeURIComponent(eid));
  const e = d.emergency;
  current = eid;
  $("#hdr").innerHTML = `<div><span class="muted small">Emergency</span><b>${esc(e.emergency_id)}</b></div><div><span class="muted small">Patient</span><b>${esc(e.patient_id)}</b></div>
    <div><span class="muted small">Ambulance</span><b>${esc(e.ambulance_id || "-")}</b></div><div><span class="muted small">Status</span><b>${badge(e.ambulance_status)}</b></div>
    <div><span class="muted small">ETA</span><b>${e.ambulance_status === "ARRIVED" ? "Arrived" : dash(e.eta_minutes, " min")}</b></div>`;
  $("#side").innerHTML = `<dl class="kv"><dt>Required bed</dt><dd>${esc(e.required_bed_type)}</dd><dt>Severity</dt><dd>${badge(e.severity)}</dd><dt>Type</dt><dd>${esc(e.emergency_type)}</dd>
    <dt>Hospital</dt><dd>${esc(ME.hospital.name)}</dd><dt>Patient</dt><dd>${esc(e.patient_id)} · ${esc(e.patient_name || "")}</dd><dt>Emergency status</dt><dd>${badge(e.status)}</dd></dl>
    <a class="btn sm" style="margin-top:10px;display:inline-block" href="/emergency-details?id=${encodeURIComponent(eid)}">Open emergency</a>`;
  $("#timeline").innerHTML = d.timeline.length ? d.timeline.map(t => `<li><div><b>${esc(t.event_type.replace(/_/g, " "))}</b>${t.new_status ? " → " + esc(t.new_status) : ""}<div class="muted small">${esc(timeOnly(t.timestamp))}</div></div></li>`).join("") : '<li class="muted">No events</li>';
  if (!tracker || tracker.emergencyId !== eid) {
    if (tracker) tracker.destroy();
    tracker = new Tracker($("#tracker"), { emergencyId: eid, ambulanceId: e.ambulance_id, onChange: () => selectEmergency(eid).catch(() => {}) });
  }
}

initPage("ambulance", "Ambulance", async () => {
  const list = await api("/api/ambulances");
  if (!list.items.length) { $("#trackerWrap").innerHTML = emptyState("No incoming ambulance right now. Receive an emergency with an ambulance first."); return; }
  const wanted = new URLSearchParams(location.search).get("id");
  const sel = $("#ambSel");
  sel.innerHTML = list.items.map(a => `<option value="${esc(a.emergency_id)}">${esc(a.emergency_id)} · ${esc(a.ambulance_id)} · ${esc(a.ambulance_status || "")}</option>`).join("");
  if (wanted && list.items.some(a => a.emergency_id === wanted)) sel.value = wanted;
  sel.onchange = () => selectEmergency(sel.value).catch(e => toast(e.message, "error"));
  await selectEmergency(sel.value);
});
