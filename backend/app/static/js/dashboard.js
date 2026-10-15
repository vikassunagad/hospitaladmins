async function load() {
  const d = await api("/api/dashboard");
  setHeaderStatus(d.hospital.status);
  const c = d.cards;
  ["total", "occupied", "reserved", "free", "icu_free", "emergency_free"].forEach(k => animateCount($("#c-" + k), c[k]));
  watchNewEmergencies(d.emergencies);
  $("#emTable").innerHTML = d.emergencies.length ? emergencyTable(d.emergencies) : emptyState("No emergencies yet. Use 'Simulate Control Room request' to create one.");
  $("#patTable").innerHTML = d.patients.length ? table(["Patient ID", "Name", "Severity", "Bed", "Status", "Arrival Time"],
    d.patients.map(p => [`<b>${esc(p.patient_id)}</b>`, esc(p.name), badge(p.severity), esc(p.assigned_bed || p.bed_type + " (reserved)"), badge(p.status), dash(p.arrival_time)])) : emptyState("No patients yet.");
  $("#alertList").innerHTML = d.alerts.length ? d.alerts.map(a => `<li><span class="dot ${esc(a.severity)}"></span><div>${esc(a.message)}<div class="muted small">${esc(timeOnly(a.created_at))}</div></div></li>`).join("") : '<li class="muted">No unread alerts</li>';
  $("#timeline").innerHTML = d.timeline.length ? d.timeline.map(t => `<li><div><b>${esc(t.event_type.replace(/_/g, " "))}</b> ${t.emergency_id ? esc(t.emergency_id) : ""}<div class="muted small">${esc(timeOnly(t.timestamp))} · ${esc(t.actor)}</div></div></li>`).join("") : '<li class="muted">No activity yet</li>';
  const a = d.ambulance;
  $("#ambPreview").innerHTML = a ? `<div class="trk-head"><span class="big">🚑 ${esc(a.ambulance_id)}</span>${badge(a.status)}</div>
      <div class="preview-road"><span style="left:${a.progress_percent}%">🚑</span></div>
      <div class="muted small">${esc(a.emergency_id)} · ETA ${a.status === "ARRIVED" ? "arrived" : dash(a.eta_minutes, " min")} · ${a.is_simulated ? "SIMULATED" : "from Control Room"}</div>
      <a class="btn primary sm" style="margin-top:10px;display:inline-block" href="/ambulance?id=${encodeURIComponent(a.emergency_id)}">Open live view</a>`
    : emptyState("No ambulance on the way.");
  $("#updated").textContent = "Last updated " + d.updated_at.slice(11);
  $("#emptyHint").hidden = true;
}

initPage("dashboard", "Dashboard", async (me) => {
  $("#emTable").innerHTML = skeleton(5);
  bindEmergencyActions($("#emTable"), load);
  if (me.config.mock_control_room) {
    $("#sampleBtn").hidden = false;
    $("#sampleBtn").onclick = () => runAction(() => sendSample($("#sampleBed").value, load));
  } else { $("#sampleBox").hidden = true; }
  poll(async () => { try { await load(); } catch (e) { $("#emTable").innerHTML = `<div class="errorbox">${esc(e.message)}</div>`; } }, 4000);
});
