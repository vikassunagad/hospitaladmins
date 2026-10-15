const TREATMENTS = "Under observation";

async function load() {
  const status = $("#statusFilter").value;
  const d = await api("/api/patients" + (status ? "?status=" + status : ""));
  $("#patTable").innerHTML = d.items.length ? table(["Patient ID", "Name", "Severity", "Bed", "Status", "Treatment", "Arrival Time", "Action"],
    d.items.map(p => [`<b>${esc(p.patient_id)}</b><div class="muted small">${esc(p.emergency_id)}</div>`, esc(p.name), badge(p.severity),
      esc(p.assigned_bed || p.bed_type + " (reserved)"), badge(p.status), dash(p.treatment_status), dash(p.arrival_time), actions(p)])) : emptyState("No patients found.");
}

function actions(p) {
  const id = esc(p.patient_id), eid = esc(p.emergency_id);
  if (p.status === "INCOMING") return `<button class="btn sm primary" data-a="arrive" data-e="${eid}">Mark arrived</button>`;
  if (p.status === "ARRIVED") return `<button class="btn sm primary" data-a="admit" data-id="${id}">Admit</button>`;
  if (p.status === "ADMITTED") return `<button class="btn sm primary" data-a="treat" data-id="${id}">Start treatment</button>`;
  if (p.status === "UNDER_TREATMENT") return `<button class="btn sm danger" data-a="discharge" data-id="${id}">Discharge</button>`;
  return '<span class="muted">-</span>';
}

initPage("patients", "Patients", async () => {
  $("#patTable").innerHTML = skeleton(5);
  $("#statusFilter").onchange = load;
  $("#patTable").addEventListener("click", async (ev) => {
    const b = ev.target.closest("button[data-a]");
    if (!b) return;
    const a = b.dataset.a, id = b.dataset.id && encodeURIComponent(b.dataset.id);
    if (a === "arrive") return runAction(() => post(`/api/emergencies/${encodeURIComponent(b.dataset.e)}/arrive`), "Patient marked as ARRIVED", load);
    if (a === "admit") return runAction(() => post(`/api/patients/${id}/admit`), "Admitted: bed RESERVED → OCCUPIED", load);
    if (a === "treat") {
      const t = await askText("Treatment status", TREATMENTS);
      if (t) return runAction(() => post(`/api/patients/${id}/treatment`, { treatment_status: t }), "Treatment started", load);
    }
    if (a === "discharge") {
      if (await confirmDialog("Discharge this patient? Their bed becomes FREE.", "Discharge"))
        return runAction(() => post(`/api/patients/${id}/discharge`), "Discharged: bed OCCUPIED → FREE", load);
    }
  });
  poll(async () => { try { await load(); } catch (e) { $("#patTable").innerHTML = `<div class="errorbox">${esc(e.message)}</div>`; } }, 4000);
});
