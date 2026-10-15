/* MapView: Leaflet + OpenStreetMap when online. If Leaflet cannot load (offline), a simple SVG map is drawn instead. */
class MapView {
  constructor(el) {
    this.el = el;
    this.fitted = false;
    this.leaflet = typeof L !== "undefined";
    if (this.leaflet) {
      this.map = L.map(el).setView([16.8302, 75.7100], 13);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap contributors" }).addTo(this.map);
      setTimeout(() => this.map.invalidateSize(), 200);
    }
  }
  icon(emoji, cls) { return L.divIcon({ html: `<div class="mk">${emoji}</div>`, className: cls || "", iconSize: [34, 34], iconAnchor: [17, 17] }); }

  update(d) {            // d = {incident:[lat,lng], hospital:[lat,lng], route:[[lat,lng]...], ambulance:[lat,lng]}
    if (this.leaflet) return this.updateLeaflet(d);
    return this.updateSvg(d);
  }

  updateLeaflet(d) {
    if (!this.layers) {
      this.layers = {
        route: L.polyline([], { color: "#0f6a80", weight: 5, opacity: .75, dashArray: "8 8" }).addTo(this.map),
        hospital: L.marker(d.hospital, { icon: this.icon("🏥") }).addTo(this.map).bindTooltip("Hospital"),
        incident: d.incident ? L.marker(d.incident, { icon: this.icon("📍") }).addTo(this.map).bindTooltip("Incident") : null,
        amb: d.ambulance ? L.marker(d.ambulance, { icon: this.icon("🚑", "amb") }).addTo(this.map).bindTooltip("Ambulance") : null,
      };
    }
    const l = this.layers;
    l.route.setLatLngs(d.route && d.route.length ? d.route : []);
    if (d.ambulance) {
      if (!l.amb) l.amb = L.marker(d.ambulance, { icon: this.icon("🚑", "amb") }).addTo(this.map);
      else l.amb.setLatLng(d.ambulance);
    }
    if (!this.fitted) {
      const pts = [d.hospital].concat(d.incident ? [d.incident] : []).concat(d.route || []);
      this.map.fitBounds(L.latLngBounds(pts), { padding: [40, 40] });
      this.fitted = true;
    }
  }

  updateSvg(d) {
    const pts = [d.hospital].concat(d.incident ? [d.incident] : []).concat(d.route || []).concat(d.ambulance ? [d.ambulance] : []);
    const lats = pts.map(p => p[0]), lngs = pts.map(p => p[1]);
    let minLat = Math.min(...lats), maxLat = Math.max(...lats), minLng = Math.min(...lngs), maxLng = Math.max(...lngs);
    const padLat = (maxLat - minLat || .01) * .15, padLng = (maxLng - minLng || .01) * .15;
    minLat -= padLat; maxLat += padLat; minLng -= padLng; maxLng += padLng;
    const W = 800, H = 480;
    const X = p => ((p[1] - minLng) / (maxLng - minLng)) * W;
    const Y = p => H - ((p[0] - minLat) / (maxLat - minLat)) * H;
    let grid = "";
    for (let i = 1; i < 10; i++) grid += `<line x1="${i * 80}" y1="0" x2="${i * 80}" y2="${H}" stroke="#cfdbe2"/><line x1="0" y1="${i * 48}" x2="${W}" y2="${i * 48}" stroke="#cfdbe2"/>`;
    const route = (d.route || []).map(p => `${X(p).toFixed(1)},${Y(p).toFixed(1)}`).join(" ");
    const mk = (p, e) => p ? `<text x="${X(p)}" y="${Y(p)}" font-size="30" text-anchor="middle" dominant-baseline="middle">${e}</text>` : "";
    this.el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style="background:#e6eef2">
      ${grid}<polyline points="${route}" fill="none" stroke="#0f6a80" stroke-width="5" stroke-dasharray="10 8" opacity=".8"/>
      ${mk(d.incident, "📍")}${mk(d.hospital, "🏥")}${mk(d.ambulance, "🚑")}
      <text x="10" y="${H - 10}" font-size="13" fill="#5b6d7b">Offline schematic map (internet needed for street map)</text></svg>`;
  }
}
