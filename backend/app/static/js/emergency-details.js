const EID = new URLSearchParams(location.search).get("id");
let tracker = null;

function actionButtons(e, hasPatient) {
  const out = [];
  if (e.status === "INCOMING") out.push(`<button class="btn primary" data-a="accept">Accept (reserve bed)</button><button class="btn danger" data-a="reject">Reject</button>`);
  if (e.status === "ACCEPTED") out.push(`<button class="btn primary" data-a="arrive" ${e.ambulance_id && e.ambulance_status !== "ARRIVED" ? "disabled title='Waiting for the ambulance to arrive'" : ""}>Patient arrived</button>`);
  if (["INCOMING", "ACCEPTED"].includes(e.status)) out.push(`<button class="btn danger" data-a="cancel">Cancel &amp; release bed</button>`);
  if (hasPatient && ["ARRIVED", "ADMITTED", "UNDER_TREATMENT"].includes(e.status)) out.push(`<a class="btn primary" href="/patients">Manage patient</a>`);
  return out.join("") || '<span class="muted">No actions available.</span>';
}

async function load() {
  if (!EID) { $("#details").innerHTML = '<div class="errorbox">No emergency selected.</div>'; return; }
  const d = await api("/api/emergencies/" + encodeURIComponent(EID));
  const e = d.emergency, p = d.patient;
  $("#title").innerHTML = `Emergency ${esc(e.emergency_id)} ${badge(e.status)}`;
  $("#details").innerHTML = `<dl class="kv">
    <dt>Patient</dt><dd>${esc(e.patient_id)} · ${esc(e.patient_name || "")}</dd>
    <dt>Type / Severity</dt><dd>${esc(e.emergency_type)} ${badge(e.severity)}</dd>
    <dt>Required bed</dt><dd>${esc(e.required_bed_type)} · ${esc(e.required_treatment || "-")}</dd>
    <dt>Bed reservation</dt><dd>${d.reservation ? badge(d.reservation) : "-"}</dd>
    <dt>Incident</dt><dd>${esc(e.incident_location || "-")}</dd>
    <dt>Ambulance</dt><dd>${e.ambulance_id ? esc(e.ambulance_id) + " " + badge(e.ambulance_status) : "-"}</dd>
    <dt>Received</dt><dd>${esc(e.received_at)}</dd>
    ${e.rejection_reason ? `<dt>Reason</dt><dd>${esc(e.rejection_reason)}</dd>` : ""}</dl>`;
  $("#actions").innerHTML = actionButtons(e, !!p);
  $("#patientBox").innerHTML = p ? `<dl class="kv"><dt>Patient ID</dt><dd>${esc(p.patient_id)}</dd><dt>Status</dt><dd>${badge(p.status)}</dd><dt>Bed</dt><dd>${esc(p.assigned_bed || "reserved, not yet admitted")}</dd><dt>Arrival</dt><dd>${dash(p.arrival_time)}</dd></dl>` : emptyState("No patient record (emergency not accepted).");
  $("#timeline").innerHTML = d.timeline.length ? d.timeline.map(t => `<li><div><b>${esc(t.event_type.replace(/_/g, " "))}</b>${t.new_status ? " → " + esc(t.new_status) : ""}<div class="muted small">${esc(timeOnly(t.timestamp))} · ${esc(t.actor)}</div></div></li>`).join("") : '<li class="muted">No events</li>';
  if (d.ambulance && !tracker) {
    $("#trackerCard").hidden = false;
    tracker = new Tracker($("#tracker"), { emergencyId: e.emergency_id, ambulanceId: e.ambulance_id, compact: true, onChange: () => load().catch(() => {}) });
    $("#fullLink").href = "/ambulance?id=" + encodeURIComponent(e.emergency_id);
  }
}

initPage("emergencies", "Emergency details", async () => {
  $("#actions").addEventListener("click", async (ev) => {
    const b = ev.target.closest("button[data-a]");
    if (!b) return;
    const a = b.dataset.a, base = "/api/emergencies/" + encodeURIComponent(EID);
    if (a === "accept") await runAction(() => post(base + "/accept"), "Bed reserved - emergency accepted", load);
    if (a === "reject") { if (await confirmDialog("Reject this emergency? The Control Room will redirect it.", "Reject")) await runAction(() => post(base + "/reject", { reason: "Rejected by hospital staff" }), "Emergency rejected", load); }
    if (a === "cancel") { if (await confirmDialog("Cancel this emergency and release the reserved bed?", "Cancel emergency")) await runAction(() => post(base + "/cancel"), "Cancelled - bed released", load); }
    if (a === "arrive") await runAction(() => post(base + "/arrive"), "Patient marked as ARRIVED", load);
  });
  try { await load(); } catch (e) { $("#details").innerHTML = `<div class="errorbox">${esc(e.message)}</div>`; }
  poll(async () => { try { await load(); } catch (e) { /* keep last view */ } }, 4000);
});
