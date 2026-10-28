// Virtual ofis: AI hodimlar yuradigan, ishlaydigan jonli 2D ofis (canvas).
const Office = (() => {
  const T = 16; // bitta katak (logik piksel)
  const SIZES = { kichik: [40, 18], orta: [54, 20], katta: [70, 22], mega: [92, 24] };
  const THEMES = {
    klassik: { wall: "#c99f9f", wallDark: "#8d6767", floor: "#f5f4f1", grid: "#ecebe6", glass: "#9cc9ff", room: "#353c6b", roomFloor: "#2a2f58", roomLine: "#4a5294", desk: "#e9c79b", deskEdge: "#c49a68", chair: "#575d7c", table: "#e9b98a", sofa: "#e7a2b6", plant: "#34d399", text: "#1f2340" },
    tungi:   { wall: "#2b3150", wallDark: "#161a2e", floor: "#1d2135", grid: "#22273d", glass: "#4f7bff", room: "#11142a", roomFloor: "#0c0f22", roomLine: "#3b438a", desk: "#3a4066", deskEdge: "#262a47", chair: "#6b72a8", table: "#4a4f7a", sofa: "#7c3aed", plant: "#10b981", text: "#e2e8f0" },
    yashil:  { wall: "#94b49f", wallDark: "#5f7f6a", floor: "#f1f6ee", grid: "#e4ede0", glass: "#a7f3d0", room: "#2f4f3e", roomFloor: "#24402f", roomLine: "#4f7a5f", desk: "#d9c3a0", deskEdge: "#a88a5f", chair: "#4b6356", table: "#c9a77c", sofa: "#86efac", plant: "#16a34a", text: "#1b3326" },
    premium: { wall: "#3a2f28", wallDark: "#1f1814", floor: "#e9dfcf", grid: "#e0d4c0", glass: "#f5d58a", room: "#2b2420", roomFloor: "#1d1815", roomLine: "#a8853e", desk: "#8a5a3b", deskEdge: "#5e3c26", chair: "#2b2b2b", table: "#7a4a2e", sofa: "#b08d57", plant: "#3f9b5a", text: "#2b1d12" },
  };
  const SKIN = ["#f1c7a5", "#e0ac84", "#c68a62", "#f6d3b8", "#a8724f"];
  const HAIR = ["#2b1d14", "#4a2f1d", "#111111", "#6b4226", "#3a3a3a", "#8a5a2b"];

  let cv, ctx, onSelect, layout = null, agents = [], selected = null, key = "", theme = THEMES.klassik, info = null;
  let scale = 1, last = 0, hover = null;

  function init(canvas, cb) {
    cv = canvas; ctx = cv.getContext("2d"); onSelect = cb;
    new ResizeObserver(resize).observe(cv.parentElement);
    cv.addEventListener("click", (e) => { const a = hit(e); if (a) onSelect(a.h.id); });
    cv.addEventListener("mousemove", (e) => { hover = hit(e); cv.style.cursor = hover ? "pointer" : "default"; });
    requestAnimationFrame(loop);
  }

  function hit(e) {
    const r = cv.getBoundingClientRect();
    const x = (e.clientX - r.left) / scale, y = (e.clientY - r.top) / scale;
    let best = null, bd = 14;
    for (const a of agents) { const d = Math.hypot(a.x - x, a.y - 10 - y); if (d < bd) { bd = d; best = a; } }
    return best;
  }

  function resize() {
    if (!layout) return;
    const w = cv.parentElement.clientWidth - 16;
    scale = w / (layout.W * T);
    const dpr = window.devicePixelRatio || 1;
    cv.width = Math.round(layout.W * T * scale * dpr);
    cv.height = Math.round(layout.H * T * scale * dpr);
    cv.style.height = layout.H * T * scale + "px";
    ctx.setTransform(scale * dpr, 0, 0, scale * dpr, 0, 0);
  }

  // ---------- Joylashuv ----------
  function build(hajm, n) {
    const [W, H] = SIZES[hajm] || SIZES.kichik;
    const L = { W, H, desks: [], pois: [], rooms: [], corridor: 8.5 * T };
    const big = hajm !== "kichik", huge = hajm === "katta" || hajm === "mega";
    let right = W - 1;
    if (huge) { L.rooms.push({ type: "gym", x: right - 9, y: 2, w: 9, h: H - 3 }); right -= 10; }
    if (big) { L.rooms.push({ type: "meet", x: right - 9, y: 2, w: 9, h: H - 3 }); right -= 10; }
    L.kitchenX = right - 6; // oshxona burchagi
    L.boss = { x: 1, y: 2, w: 9, h: 6 };
    L.round = { x: Math.round((11 + L.kitchenX) / 2) * T, y: 5 * T };

    // Stollar to'ri
    const x0 = 12, x1 = right - 1, y0 = 10, y1 = H - 2;
    let dx = 5, dy = 3;
    let cols = Math.max(1, Math.floor((x1 - x0) / dx)), rows = Math.max(1, Math.floor((y1 - y0) / dy));
    if (cols * rows < n) { dx = 4; cols = Math.max(1, Math.floor((x1 - x0) / dx)); }
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const dxp = (x0 + c * dx) * T, dyp = (y0 + r * dy) * T;
      L.desks.push({ x: dxp, y: dyp, seat: { x: dxp + 1.5 * T, y: dyp + 2.1 * T }, aisle: dyp + 2.6 * T, gap: dxp - 0.6 * T });
    }
    // Sayr qilinadigan joylar
    const corY = L.corridor;
    L.pois.push({ name: "kofe", x: (L.kitchenX + 2) * T, y: 4.2 * T, entry: { x: (L.kitchenX + 2) * T, y: corY } });
    L.pois.push({ name: "suv", x: (L.kitchenX + 4.5) * T, y: 4.2 * T, entry: { x: (L.kitchenX + 4.5) * T, y: corY } });
    for (const [ox, oy] of [[-1.6, 0.2], [1.6, 0.2], [0, 1.6]]) L.pois.push({ name: "stol", x: L.round.x + ox * T, y: L.round.y + oy * T, entry: { x: L.round.x + ox * T, y: corY } });
    L.pois.push({ name: "divan", x: 5 * T, y: (H - 3) * T, entry: { x: 10.5 * T, y: corY }, via: { x: 10.5 * T, y: (H - 3) * T } });
    for (const r of L.rooms) {
      const door = { x: r.x * T - 0.5 * T, y: corY };
      for (let i = 0; i < 4; i++) {
        const px = (r.x + 2 + (i % 2) * 5) * T, py = (r.y + 4 + Math.floor(i / 2) * 6) * T;
        L.pois.push({ name: r.type, x: px, y: py, entry: door, via: { x: (r.x + 1) * T, y: corY } });
      }
    }
    return L;
  }

  function hash(s) { let h = 0; for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) | 0; return Math.abs(h); }

  function load(ofis) {
    info = ofis;
    theme = THEMES[ofis.dizayn] || THEMES.klassik;
    const k = ofis.id + ofis.hajm + ofis.hodimlar.map((h) => h.id).join(",");
    if (k !== key) {
      key = k;
      layout = build(ofis.hajm, ofis.hodimlar.length);
      const old = new Map(agents.map((a) => [a.h.id, a]));
      agents = ofis.hodimlar.slice(0, layout.desks.length).map((h, i) => {
        const d = layout.desks[i], o = old.get(h.id), s = hash(h.id + h.ism);
        return o ? Object.assign(o, { h, desk: d }) : {
          h, desk: d, x: d.seat.x, y: d.seat.y, path: [], mode: "sit", wait: 2 + (s % 8), phase: 0,
          skin: SKIN[s % SKIN.length], hair: HAIR[(s >> 3) % HAIR.length], long: s % 2 === 0,
        };
      });
      resize();
    } else {
      const m = new Map(ofis.hodimlar.map((h) => [h.id, h]));
      for (const a of agents) a.h = m.get(a.h.id) || a.h;
    }
  }

  function select(id) { selected = id; }

  // ---------- Harakat ----------
  function routeFromSeat(a, poi) {
    const d = a.desk, pts = [{ x: d.seat.x, y: d.aisle }, { x: d.gap, y: d.aisle }, { x: d.gap, y: layout.corridor }];
    if (poi.via) pts.push({ x: poi.via.x, y: layout.corridor }, poi.via);
    pts.push({ x: poi.entry.x, y: poi.entry.y === layout.corridor ? layout.corridor : poi.entry.y });
    pts.push({ x: poi.x, y: poi.y });
    return pts;
  }

  function update(dt) {
    for (const a of agents) {
      const busy = a.h.holat === "ishlayapti" || a.h.holat === "suhbatda";
      if (a.path.length) {
        const p = a.path[0], vx = p.x - a.x, vy = p.y - a.y, dist = Math.hypot(vx, vy);
        const sp = (busy ? 90 : 45) * dt;
        if (dist <= sp) { a.x = p.x; a.y = p.y; a.path.shift(); }
        else { a.x += (vx / dist) * sp; a.y += (vy / dist) * sp; }
        a.phase += dt * 10;
        if (!a.path.length) { a.mode = a.mode === "going" ? "visit" : "sit"; a.wait = a.mode === "visit" ? 4 + Math.random() * 6 : 8 + Math.random() * 14; }
        continue;
      }
      if (busy && a.mode !== "sit") { a.path = a.back || []; a.mode = "return"; continue; }
      a.wait -= dt;
      if (a.wait > 0 || busy) continue;
      if (a.mode === "sit") {
        if (Math.random() < 0.45) {
          const poi = layout.pois[Math.floor(Math.random() * layout.pois.length)];
          a.path = routeFromSeat(a, poi); a.back = a.path.slice(0, -1).reverse().concat([{ x: a.desk.seat.x, y: a.desk.seat.y }]); a.mode = "going";
        } else a.wait = 6 + Math.random() * 10;
      } else if (a.mode === "visit") { a.path = a.back; a.mode = "return"; }
    }
  }

  // ---------- Chizish ----------
  const R = (x, y, w, h, c) => { ctx.fillStyle = c; ctx.fillRect(x, y, w, h); };
  function round(x, y, w, h, r, c) { ctx.fillStyle = c; ctx.beginPath(); ctx.roundRect(x, y, w, h, r); ctx.fill(); }
  function plant(x, y) { R(x - 4, y, 8, 7, "#b45309"); ctx.fillStyle = theme.plant; for (const [ox, oy] of [[-4, -3], [4, -3], [0, -7], [0, -1]]) { ctx.beginPath(); ctx.arc(x + ox, y + oy, 4, 0, 7); ctx.fill(); } }

  function drawStatic() {
    const { W, H } = layout, t = theme;
    R(0, 0, W * T, H * T, t.floor);
    ctx.strokeStyle = t.grid; ctx.lineWidth = 1;
    for (let x = 0; x < W; x++) { ctx.beginPath(); ctx.moveTo(x * T, 2 * T); ctx.lineTo(x * T, H * T); ctx.stroke(); }
    // Devorlar
    R(0, 0, W * T, 2 * T, t.wall); R(0, 0, W * T, 4, t.wallDark);
    R(0, 0, 6, H * T, t.wall); R(W * T - 6, 0, 6, H * T, t.wall); R(0, H * T - 8, W * T, 8, t.wall);
    // Devordagi narsalar: soat-tablo, doska, kompaniya nomi
    const now = new Date(), hh = String(now.getHours()).padStart(2, "0"), mm = String(now.getMinutes()).padStart(2, "0");
    const cx = Math.round(W / 2) * T;
    round(cx - 50, 4, 100, 22, 4, "#111"); ctx.fillStyle = "#facc15"; ctx.font = "bold 13px monospace"; ctx.textAlign = "center";
    ctx.fillText(`${hh}:${mm}  ${(info && info.mijoz || "").slice(0, 10).toUpperCase()}`, cx, 20);
    R(14 * T, 6, 4 * T, 18, "#f8fafc"); R(14 * T, 6, 4 * T, 3, "#94a3b8");
    R((layout.kitchenX - 3) * T, 6, 2 * T, 20, "#1e293b"); R((layout.kitchenX - 3) * T + 3, 9, 2 * T - 6, 12, "#38bdf8");

    // Rahbar kabineti (shisha xona)
    const b = layout.boss;
    ctx.fillStyle = t.glass + "33"; ctx.fillRect(b.x * T, b.y * T, b.w * T, b.h * T);
    ctx.strokeStyle = t.glass; ctx.lineWidth = 3; ctx.strokeRect(b.x * T + 2, b.y * T, b.w * T - 4, b.h * T);
    R((b.x + 2) * T, (b.y + 2) * T, 4 * T, T * 1.2, t.desk); R((b.x + 3.2) * T, (b.y + 2) * T + 2, T * 1.4, 8, "#334155");
    ctx.fillStyle = t.chair; ctx.beginPath(); ctx.arc((b.x + 4) * T, (b.y + 1.4) * T, 6, 0, 7); ctx.fill();
    R((b.x + 6.5) * T, (b.y + 3.5) * T, T * 1.6, T * 1.6, "#2563eb");
    // Divan
    round(2 * T, (H - 4) * T, 6 * T, 1.6 * T, 6, t.sofa); round(2 * T, (H - 4.4) * T, 6 * T, 0.7 * T, 4, t.wallDark);
    plant(1.2 * T, (H - 2) * T); plant(9 * T, 3 * T);

    // Oshxona: muzlatgich, kofe mashina, kuler
    const kx = layout.kitchenX * T;
    R(kx, 2 * T, 7 * T, 1.2 * T, "#cbd5e1");
    R(kx + 2, 2 * T - 8, T * 1.3, 2.4 * T, "#e2e8f0"); R(kx + 2, 2 * T + 10, T * 1.3, 2, "#94a3b8");
    R(kx + 1.6 * T, 2 * T + 2, T, T * 0.8, "#1f2937"); R(kx + 1.9 * T, 2 * T + 6, 6, 4, "#ef4444");
    R(kx + 4 * T, 2 * T + 2, T * 0.9, T * 1.3, "#bae6fd"); R(kx + 4 * T + 3, 2 * T - 6, T * 0.6, 9, "#38bdf8");
    plant(kx + 6.5 * T, 3.4 * T);

    // Davra stol
    const rd = layout.round;
    ctx.fillStyle = t.table; ctx.beginPath(); ctx.ellipse(rd.x, rd.y, 2.4 * T, 1.3 * T, 0, 0, 7); ctx.fill();
    ctx.fillStyle = t.chair; for (const [ox, oy] of [[-2.9, 0], [2.9, 0], [0, 1.9], [-1.4, -1.6], [1.4, -1.6]]) { ctx.beginPath(); ctx.arc(rd.x + ox * T, rd.y + oy * T, 5, 0, 7); ctx.fill(); }

    // Xonalar
    for (const r of layout.rooms) {
      R(r.x * T, r.y * T, r.w * T, r.h * T, t.roomLine);
      R(r.x * T + 4, r.y * T + 4, r.w * T - 8, r.h * T - 8, t.room);
      for (let i = 0; i < r.w; i += 1) R(r.x * T + 4 + i * T, r.y * T + 4, 1, r.h * T - 8, t.roomFloor);
      R(r.x * T, layout.corridor - 10, 4, 22, t.floor); // eshik
      if (r.type === "meet") {
        R((r.x + 2) * T, (r.y + 3) * T, 5 * T, (r.h - 6) * T, t.table);
        for (let i = 0; i < r.h - 7; i += 2) { ctx.fillStyle = t.chair; for (const sx of [r.x + 1.5, r.x + 7.5]) { ctx.beginPath(); ctx.arc(sx * T, (r.y + 4 + i) * T, 5, 0, 7); ctx.fill(); } }
        R((r.x + 2.5) * T, r.y * T + 6, 4 * T, 10, "#0f172a"); R((r.x + 2.7) * T, r.y * T + 8, 3.6 * T, 6, "#60a5fa");
      } else {
        for (let i = 0; i < 3; i++) { R((r.x + 1.5) * T, (r.y + 3 + i * 5) * T, 1.6 * T, 3 * T, "#1e293b"); R((r.x + 1.8) * T, (r.y + 3.4 + i * 5) * T, T, 2.2 * T, "#64748b"); }
        R((r.x + 5.5) * T, (r.y + 3) * T, 2 * T, 2 * T, "#2563eb"); R((r.x + 5.5) * T, (r.y + 10) * T, 2 * T, 2 * T, "#2563eb");
        R((r.x + 3) * T, (r.y + r.h - 3) * T, 3 * T, T, "#22d3ee");
      }
      plant((r.x + r.w - 1.5) * T, (r.y + r.h - 1.5) * T);
    }
  }

  function drawDesk(d, busy) {
    R(d.x, d.y, 3 * T, 1.15 * T, theme.desk); R(d.x, d.y + 1.15 * T - 3, 3 * T, 3, theme.deskEdge);
    R(d.x + 0.9 * T, d.y + 1, 1.2 * T, 0.75 * T, "#334155");
    R(d.x + 0.9 * T + 2, d.y + 3, 1.2 * T - 4, 0.75 * T - 5, busy ? "#38bdf8" : "#64748b");
    R(d.x + 0.9 * T + 4, d.y + 0.85 * T, 1.2 * T - 8, 3, "#cbd5e1");
  }

  function drawAgent(a, time) {
    const { x, y } = a, walking = a.path.length > 0, sitting = !walking && Math.hypot(x - a.desk.seat.x, y - a.desk.seat.y) < 1;
    const sw = walking ? Math.sin(a.phase) * 2.5 : 0;
    ctx.fillStyle = "#0002"; ctx.beginPath(); ctx.ellipse(x, y + 1, 6, 2.5, 0, 0, 7); ctx.fill();
    if (sitting) { ctx.fillStyle = theme.chair; ctx.beginPath(); ctx.arc(x, y - 2, 7, 0, 7); ctx.fill(); }
    else { R(x - 4, y - 7 + sw, 3, 7 - sw, "#1f2937"); R(x + 1, y - 7 - sw, 3, 7 + sw, "#1f2937"); }
    const by = sitting ? y - 4 : y - 7;
    round(x - 5.5, by - 9, 11, 10, 3, a.h.rang || "#6366f1");
    ctx.fillStyle = a.skin; ctx.beginPath(); ctx.arc(x, by - 13, 4.6, 0, 7); ctx.fill();
    ctx.fillStyle = a.hair; ctx.beginPath(); ctx.arc(x, by - 14.2, 4.8, Math.PI, 0); ctx.fill();
    if (a.long) R(x - 4.8, by - 14, 2.2, 7, a.hair), R(x + 2.6, by - 14, 2.2, 7, a.hair);
    if (sitting) { ctx.fillStyle = a.hair; ctx.beginPath(); ctx.arc(x, by - 13, 4.8, 0, 7); ctx.fill(); } // orqadan ko'rinish

    // Ism yorlig'i
    const label = a.h.ism, sel = a.h.id === selected || hover === a;
    ctx.font = "bold 8px system-ui"; ctx.textAlign = "center";
    const w = ctx.measureText(label).width + 10;
    round(x - w / 2, by - 31, w, 11, 3, sel ? "#6d7cff" : "#1f2340dd");
    ctx.fillStyle = "#fff"; ctx.fillText(label, x, by - 23);
    // Holat pufakchasi
    if (a.h.holat === "ishlayapti" && sitting) {
      ctx.font = "10px system-ui"; ctx.fillText("💻", x + w / 2 + 6, by - 22);
      const dots = ".".repeat(1 + (Math.floor(time * 3) % 3)); ctx.fillStyle = "#22c55e"; ctx.font = "bold 9px monospace"; ctx.fillText(dots, x, by - 34);
    } else if (a.h.holat === "suhbatda") { ctx.font = "10px system-ui"; ctx.fillText("💬", x + w / 2 + 6, by - 22); }
    else if (a.mode === "visit") { ctx.font = "9px system-ui"; ctx.fillText(a.h.emoji || "☕", x + w / 2 + 6, by - 22); }
  }

  function loop(ts) {
    const dt = Math.min(0.05, (ts - last) / 1000 || 0); last = ts;
    if (layout) {
      update(dt);
      drawStatic();
      for (const d of layout.desks.slice(0, agents.length)) { const a = agents.find((g) => g.desk === d); drawDesk(d, a && a.h.holat === "ishlayapti"); }
      for (const d of layout.desks.slice(agents.length)) drawDesk(d, false);
      [...agents].sort((p, q) => p.y - q.y).forEach((a) => drawAgent(a, ts / 1000));
    }
    requestAnimationFrame(loop);
  }

  return { init, load, select, capacity: (hajm) => build(hajm, 0).desks.length };
})();
