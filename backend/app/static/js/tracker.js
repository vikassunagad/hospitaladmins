/* Tracker: the ambulance live-view panel (READ-ONLY view of Control Room data).
   Demo buttons only appear when the backend says simulation is available (mock mode). */
class Tracker {
  constructor(root, opts) {
    this.root = root; this.emergencyId = opts.emergencyId; this.ambulanceId = opts.ambulanceId;
    this.onChange = opts.onChange || (() => {}); this.compact = !!opts.compact;
    this.running = false; this.timer = null; this.lastStatus = null;
    root.innerHTML = `
      <div class="trk-head">
        <span class="big">🚑 <span class="t-amb">-</span></span><span class="t-status"></span>
        <span class="t-banner"></span><span class="sp" style="flex:1"></span>
        <span class="actions t-demo" hidden>
          <button class="btn primary sm t-start">▶ START SIMULATION</button>
          <button class="btn sm t-pause">⏸ PAUSE</button>
          <button class="btn sm t-reset">↺ RESET</button>
        </span>
      </div>
      <div class="trk-map ${this.compact ? "compact" : ""}"></div>
      <div class="progress"><i class="t-bar" style="width:0"></i></div>
      <div class="trk-stats">
        <div><span class="muted small">ETA</span><b class="t-eta">-</b></div>
        <div><span class="muted small">Distance left</span><b class="t-dist">-</b></div>
        <div><span class="muted small">Route progress</span><b class="t-prog">-</b></div>
        <div><span class="muted small">Last updated</span><b class="t-upd">-</b></div>
      </div>
      <div class="t-note muted small" style="margin-top:8px"></div>`;
    this.map = new MapView($(".trk-map", root));
    $(".t-start", root).onclick = () => this.start();
    $(".t-pause", root).onclick = () => this.pause();
    $(".t-reset", root).onclick = () => this.reset();
    this.refresh();
    this.poller = setInterval(() => { if (!this.running) this.refresh(); }, 3000);
  }
  q(s) { return $(s, this.root); }
  url() { return `/api/ambulances/${encodeURIComponent(this.ambulanceId)}?emergency_id=${encodeURIComponent(this.emergencyId)}`; }

  async refresh() {
    try { this.render(await api(this.url())); } catch (e) { this.q(".t-note").textContent = e.message; }
  }

  render(v) {
    this.view = v;
    this.q(".t-amb").textContent = v.ambulance_id;
    this.q(".t-status").innerHTML = badge(v.status);
    this.q(".t-banner").innerHTML = v.is_simulated
      ? '<span class="trk-banner sim">DEMO / SIMULATED AMBULANCE TRACKING</span>'
      : '<span class="trk-banner real">Location received from Control Room</span>';
    this.q(".t-eta").textContent = v.status === "ARRIVED" ? "Arrived" : (v.eta_minutes == null ? "-" : v.eta_minutes + " min");
    this.q(".t-dist").textContent = v.distance_km == null ? "-" : Number(v.distance_km).toFixed(1) + " km";
    this.q(".t-prog").textContent = v.progress_percent + "%";
    this.q(".t-bar").style.width = v.progress_percent + "%";
    this.q(".t-upd").textContent = timeOnly(v.last_updated);
    this.q(".t-demo").hidden = !v.demo_available;
    this.q(".t-note").textContent = v.status === "NEAR_HOSPITAL" ? "Approaching hospital" : (v.status === "ARRIVED" ? "Ambulance arrived - patient workflow can proceed" : "");
    this.map.update({ incident: v.incident, hospital: v.hospital.position, route: v.route, ambulance: v.position });
    if (v.status !== this.lastStatus) { this.lastStatus = v.status; this.onChange(v); }
  }

  async step() {
    try {
      const v = await post(`/api/integration/mock/emergencies/${encodeURIComponent(this.emergencyId)}/simulate/step`);
      this.render(v);
      if (v.status === "ARRIVED") { this.pause(); toast("Ambulance arrived at hospital", "success"); }
    } catch (e) { this.pause(); toast(e.message, "error"); }
  }
  start() { if (this.running) return; this.running = true; this.step(); this.timer = setInterval(() => this.step(), 1200); }
  pause() { this.running = false; clearInterval(this.timer); }
  async reset() {
    this.pause();
    try { this.render(await post(`/api/integration/mock/emergencies/${encodeURIComponent(this.emergencyId)}/simulate/reset`)); toast("Simulation reset"); }
    catch (e) { toast(e.message, "error"); }
  }
  destroy() { this.pause(); clearInterval(this.poller); }
}
