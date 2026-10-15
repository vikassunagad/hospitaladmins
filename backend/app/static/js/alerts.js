async function load() {
  const d = await api("/api/alerts");
  $("#alertList").innerHTML = d.items.length ? d.items.map(a => `<li style="${a.is_read ? "opacity:.55" : ""}"><span class="dot ${esc(a.severity)}"></span>
    <div style="flex:1"><b>${esc(a.alert_type.replace(/_/g, " "))}</b> ${a.emergency_id ? `· <a href="/emergency-details?id=${encodeURIComponent(a.emergency_id)}">${esc(a.emergency_id)}</a>` : ""}
    <div>${esc(a.message)}</div><div class="muted small">${esc(a.created_at)}</div></div>
    ${a.is_read ? "" : `<button class="btn sm" data-read="${a.id}">Mark read</button>`}</li>`).join("") : emptyState("No alerts.");
  $("#unreadInfo").textContent = d.unread + " unread";
  updateBadge();
}

initPage("alerts", "Alerts", async () => {
  $("#alertList").innerHTML = skeleton(4);
  $("#alertList").addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-read]");
    if (b) runAction(() => post(`/api/alerts/${b.dataset.read}/read`), null, load);
  });
  $("#readAll").onclick = () => runAction(() => post("/api/alerts/read-all"), "All alerts marked read", load);
  poll(async () => { try { await load(); } catch (e) { $("#alertList").innerHTML = `<div class="errorbox">${esc(e.message)}</div>`; } }, 5000);
});
