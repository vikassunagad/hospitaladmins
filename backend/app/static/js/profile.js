initPage("profile", "Profile", async (me) => {
  const cap = await api("/api/capacity");
  const t = cap.capacity.TOTAL;
  $("#profileBox").innerHTML = `<dl class="kv"><dt>Hospital</dt><dd>${esc(me.hospital.name)}</dd><dt>Hospital ID</dt><dd>${esc(me.hospital.id)}</dd>
    <dt>Username</dt><dd>${esc(me.user.username)}</dd><dt>Role</dt><dd>${esc(me.user.role)}</dd><dt>Status</dt><dd>${badge(me.hospital.status)}</dd>
    <dt>Total beds</dt><dd>${t.total} (occupied ${t.occupied}, reserved ${t.reserved}, free ${t.free})</dd></dl>`;
  $("#configBox").innerHTML = `<dl class="kv"><dt>Control Room mode</dt><dd>${me.config.mock_control_room ? "MOCK (local)" : "LIVE (HTTP)"}</dd>
    <dt>Auto accept</dt><dd>${me.config.auto_accept ? "ON - bed reserved automatically on arrival" : "OFF - staff press Accept"}</dd>
    <dt>HIGH LOAD at</dt><dd>${me.config.high_load_threshold}%</dd><dt>CRITICAL at</dt><dd>${me.config.critical_load_threshold}%</dd></dl>`;
});
