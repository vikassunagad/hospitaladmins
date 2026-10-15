async function load() {
  const status = $("#statusFilter").value;
  const d = await api("/api/emergencies" + (status ? "?status=" + status : ""));
  if (!status) watchNewEmergencies(d.items);
  $("#emTable").innerHTML = d.items.length ? emergencyTable(d.items) : emptyState("No emergencies found.");
}

initPage("emergencies", "Emergencies", async (me) => {
  $("#emTable").innerHTML = skeleton(5);
  bindEmergencyActions($("#emTable"), load);
  $("#statusFilter").onchange = load;
  if (me.config.mock_control_room) {
    $("#mockBox").hidden = false;
    $("#sampleBtn").onclick = () => runAction(() => sendSample($("#sampleBed").value, load));
  }
  poll(async () => { try { await load(); } catch (e) { $("#emTable").innerHTML = `<div class="errorbox">${esc(e.message)}</div>`; } }, 4000);
});
