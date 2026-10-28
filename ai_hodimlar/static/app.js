// Admin panel mantiqi (o'zbek tilida).
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let KAT = null, ofisId = null, hodimId = null, ofisData = null;

function token() { try { return localStorage.getItem("adminToken") || ""; } catch { return ""; } }
async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: { "Content-Type": "application/json", "X-Admin-Token": token(), ...(opts.headers || {}) },
    body: opts.body && typeof opts.body !== "string" && !(opts.body instanceof FormData) ? JSON.stringify(opts.body) : opts.body,
  });
  if (res.status === 401) {
    const t = prompt("Admin parolini (ADMIN_TOKEN) kiriting:");
    if (t) { try { localStorage.setItem("adminToken", t); } catch {} return api(path, opts); }
  }
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.headers.get("content-type")?.includes("json") ? res.json() : res;
}
const sh = (id) => KAT.shablonlar.find((s) => s.id === id);

// ---------- Navigatsiya ----------
document.querySelectorAll("#menu button").forEach((b) => b.onclick = () => {
  document.querySelectorAll("#menu button, .view").forEach((e) => e.classList.remove("active"));
  b.classList.add("active"); $("#v-" + b.dataset.view).classList.add("active");
  ({ mijozlar: loadMijozlar, katalog: renderKatalog, komplektlar: renderKomplektlar, bilim: loadBilim, ofislar: loadOfislar })[b.dataset.view]?.();
});
document.querySelectorAll(".tabs button").forEach((b) => b.onclick = () => {
  document.querySelectorAll(".tabs button, .tab").forEach((e) => e.classList.remove("active"));
  b.classList.add("active"); $("#t-" + b.dataset.tab).classList.add("active");
  if (b.dataset.tab === "vazifa") loadVazifalar();
});

// ---------- Ofislar ----------
async function loadOfislar() {
  const list = await api("/api/ofislar");
  $("#ofisTanla").innerHTML = list.map((o) => `<option value="${o.id}">${esc(o.mijoz)} — ${esc(o.nom)} (${o.soni})</option>`).join("");
  $("#bosh").classList.toggle("show", !list.length);
  if (!list.length) return;
  if (!list.find((o) => o.id == ofisId)) ofisId = list[0].id;
  $("#ofisTanla").value = ofisId;
  await refreshOfis();
}
async function refreshOfis() {
  if (!ofisId) return;
  ofisData = await api("/api/ofislar/" + ofisId);
  Office.load(ofisData);
  $("#dizaynTanla").value = ofisData.dizayn; $("#hajmTanla").value = ofisData.hajm;
  const ish = ofisData.hodimlar.filter((h) => h.holat === "ishlayapti").length;
  const sig = Office.capacity(ofisData.hajm);
  $("#ofisStat").textContent = `${ofisData.hodimlar.length}/${sig} hodim · ${ish} ishlayapti · ${ofisData.telegram_chat_id ? "📲 ulangan" : "📲 —"}`;
  $("#hodimRoyxat").innerHTML = ofisData.hodimlar.map((h) =>
    `<span class="chip" data-id="${h.id}"><span class="dot ${h.holat}"></span>${h.emoji} ${esc(h.ism)} <span class="muted">${esc(h.lavozim)}</span></span>`).join("");
  document.querySelectorAll(".chip").forEach((c) => c.onclick = () => openHodim(+c.dataset.id));
  loadTopshiriqlar();
}
async function loadTopshiriqlar() {
  const ts = await api(`/api/ofislar/${ofisId}/topshiriqlar`);
  const belgi = { yangi: "⏳ navbatda", jarayonda: "⚙️ jamoa ishlayapti", bajarildi: "✅ bajarildi", xato: "❌ xato", uzildi: "⛔ uzildi" };
  const vb = { yangi: "⏳", jarayonda: "⚙️", bajarildi: "✅", xato: "❌" };
  $("#topshiriqlar").innerHTML = ts.map((t) => `<div class="card tsh ${t.holat}"><b>${esc(t.matn)}</b>
    <div class="small muted">${belgi[t.holat] || t.holat} · ${esc(t.created)}${t.chat_id ? " · 📲 Telegram" : ""}</div>
    ${t.vazifalar.length ? `<ul>${t.vazifalar.map((v) => `<li>${vb[v.holat] || ""} <b>${esc(v.ism)}</b> (${esc(sh(v.shablon_id).nom)}): ${esc(v.matn)}
      ${v.natija ? `<details><summary class="small">Natija</summary><pre>${esc(v.natija)}</pre></details>` : ""}</li>`).join("")}</ul>` : ""}
    ${t.hisobot ? `<details ${t.vazifalar.length ? "" : "open"}><summary>📊 Direktor hisoboti</summary><pre>${esc(t.hisobot)}</pre></details>` : ""}</div>`).join("")
    || `<div class="muted">Hali topshiriq yo'q. "🎯 Direktorga topshiriq" tugmasini bosing yoki Telegram guruhga yozing.</div>`;
}
$("#topshiriqBtn").onclick = () => {
  if (!ofisId) return alert("Avval ofis yarating");
  const d = ofisData.hodimlar.find((h) => h.shablon_id === "direktor");
  dialog(`<h3>🎯 ${esc(d ? d.ism : "Direktor")}ga topshiriq</h3><p class="muted small">Direktor topshiriqni bo'laklarga ajratadi, jamoaga taqsimlaydi va yakuniy hisobot beradi.</p>
    <textarea name="matn" rows="5" placeholder="Masalan: Yangi yil aksiyasi uchun reklama kampaniyasini tayyorlang"></textarea>
    <div class="row"><button value="ok">Topshirish</button><button value="" class="danger">Bekor</button></div>`, async (f) => {
    if (!f.matn.value.trim()) return;
    await api(`/api/ofislar/${ofisId}/topshiriq`, { method: "POST", body: { matn: f.matn.value } }); refreshOfis();
  });
};
$("#telegramBtn").onclick = () => {
  const tg = ofisData.telegram, ulangan = !!ofisData.telegram_chat_id;
  dialog(`<h3>📲 Telegram guruh</h3>
    ${tg.yoqilgan ? "" : `<p style="color:#f87171">Serverda AI_HODIM_BOT_TOKEN o'rnatilmagan. BotFather'dan bot yarating va tokenni qo'shing.</p>`}
    <p>Holat: <b>${ulangan ? "✅ guruh ulangan" : "ulanmagan"}</b></p>
    <ol><li>Biznesmen guruh ochadi va ${tg.bot ? "<b>@" + esc(tg.bot) + "</b>" : "botni"} qo'shib, admin qiladi.</li>
    <li>Guruhga yozadi: <pre>/ulash ${esc(ofisData.ulash_kodi)}</pre></li>
    <li>Shundan keyin guruhdagi har bir xabar (matn yoki 🎤 ovoz) direktorga boradi. "Ism, ..." deb yozilsa, shu hodim javob beradi.</li></ol>
    <div class="row"><button value="">Yopish</button></div>`, () => {});
};
$("#ofisTanla").onchange = (e) => { ofisId = +e.target.value; refreshOfis(); };
$("#dizaynTanla").onchange = async (e) => { await api(`/api/ofislar/${ofisId}`, { method: "PATCH", body: { dizayn: e.target.value } }); refreshOfis(); };
$("#hajmTanla").onchange = async (e) => {
  if (Office.capacity(e.target.value) < ofisData.hodimlar.length) { alert("Bu ofisga hamma hodim sig'maydi. Kattaroq hajm tanlang."); e.target.value = ofisData.hajm; return; }
  await api(`/api/ofislar/${ofisId}`, { method: "PATCH", body: { hajm: e.target.value } }); refreshOfis();
};
$("#hodimQoshBtn").onclick = () => {
  if (!ofisId) return alert("Avval ofis yarating");
  dialog(`<h3>Ofisga hodim qo'shish</h3>
    <select name="sh">${KAT.shablonlar.map((s) => `<option value="${s.id}">${s.emoji} ${esc(s.nom)}</option>`).join("")}</select>
    <div class="row"><button value="ok">Qo'shish</button><button value="" class="danger">Bekor</button></div>`, async (f) => {
    if (Office.capacity(ofisData.hajm) <= ofisData.hodimlar.length) return alert("Ofis to'la. Hajmni kattalashtiring.");
    await api("/api/hodimlar", { method: "POST", body: { ofis_id: ofisId, shablon_id: f.sh.value } }); refreshOfis();
  });
};
setInterval(() => { if ($("#v-ofislar").classList.contains("active")) refreshOfis().catch(() => {}); }, 4000);

// ---------- Hodim paneli ----------
async function openHodim(id) {
  hodimId = id; Office.select(id);
  const h = ofisData.hodimlar.find((x) => x.id === id), s = sh(h.shablon_id);
  $("#panel").classList.remove("hidden");
  $("#pAvatar").textContent = h.emoji; $("#pAvatar").style.background = h.rang;
  $("#pIsm").textContent = h.ism; $("#pLavozim").textContent = h.lavozim;
  $("#sIsm").value = h.ism; $("#sInstr").value = h.qoshimcha_instruksiya || ""; $("#sBaza").textContent = s.instruksiya;
  const msgs = await api(`/api/hodimlar/${id}/xabarlar`);
  $("#chat").innerHTML = msgs.length ? "" : `<div class="muted">Salom! Men ${esc(h.ism)}, ${esc(h.lavozim)}. ${esc(s.tavsif)}</div>`;
  msgs.forEach((m) => addMsg(m.rol, m.matn));
  if ($("#t-vazifa").classList.contains("active")) loadVazifalar();
}
$("#pYop").onclick = () => { $("#panel").classList.add("hidden"); Office.select(null); };
function addMsg(rol, matn, cls = "") {
  const d = document.createElement("div"); d.className = `msg ${rol} ${cls}`; d.textContent = matn;
  $("#chat").append(d); $("#chat").scrollTop = 1e9; return d;
}
$("#chatForm").onsubmit = async (e) => {
  e.preventDefault();
  const matn = $("#chatInput").value.trim(); if (!matn) return;
  $("#chatInput").value = ""; addMsg("user", matn);
  const w = addMsg("assistant", "yozmoqda...", "wait");
  try {
    const { javob } = await api(`/api/hodimlar/${hodimId}/suhbat`, { method: "POST", body: { matn } });
    w.textContent = javob; w.classList.remove("wait");
    if ($("#ovozJavob").checked) gapir(javob);
  } catch (err) { w.textContent = "Xato: " + err.message; }
};

async function loadVazifalar() {
  if (!hodimId) return;
  const list = await api(`/api/hodimlar/${hodimId}/vazifalar`);
  const holat = { yangi: "⏳ navbatda", jarayonda: "⚙️ bajarilmoqda", bajarildi: "✅ bajarildi", xato: "❌ xato" };
  $("#vazifalar").innerHTML = list.map((v) => `<div class="vazifa ${v.holat}"><b>${esc(v.matn)}</b>
    <div class="small muted">${holat[v.holat]} · ${esc(v.created)}</div>${v.natija ? `<details><summary>Natija</summary><pre>${esc(v.natija)}</pre></details>` : ""}</div>`).join("")
    || `<div class="muted">Hali vazifa yo'q.</div>`;
  if (list.some((v) => v.holat === "yangi" || v.holat === "jarayonda")) setTimeout(loadVazifalar, 3000);
}
$("#vazifaForm").onsubmit = async (e) => {
  e.preventDefault(); const matn = $("#vazifaInput").value.trim(); if (!matn) return;
  await api(`/api/hodimlar/${hodimId}/vazifalar`, { method: "POST", body: { matn } });
  $("#vazifaInput").value = ""; loadVazifalar(); refreshOfis();
};
$("#sSaqla").onclick = async () => {
  await api(`/api/hodimlar/${hodimId}`, { method: "PATCH", body: { ism: $("#sIsm").value, qoshimcha_instruksiya: $("#sInstr").value } });
  await refreshOfis(); openHodim(hodimId);
};
$("#sOchir").onclick = async () => {
  if (!confirm("Hodimni o'chirasizmi?")) return;
  await api(`/api/hodimlar/${hodimId}`, { method: "DELETE" }); $("#pYop").click(); refreshOfis();
};

// ---------- O'zbekcha ovoz ----------
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let rec = null, mediaRec = null;
$("#mic").onclick = async () => {
  const mic = $("#mic");
  if (rec || (mediaRec && mediaRec.state === "recording")) { rec ? rec.stop() : mediaRec.stop(); return; }
  if (SR) {
    rec = new SR(); rec.lang = "uz-UZ"; rec.interimResults = true;
    rec.onresult = (e) => { $("#chatInput").value = [...e.results].map((r) => r[0].transcript).join(""); };
    rec.onend = () => { rec = null; mic.classList.remove("rec"); if ($("#chatInput").value.trim()) $("#chatForm").requestSubmit(); };
    rec.onerror = () => { rec = null; mic.classList.remove("rec"); };
    rec.start(); mic.classList.add("rec");
    return;
  }
  // Brauzer tanimasa: yozib olib serverga (Whisper) yuboramiz
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const chunks = []; mediaRec = new MediaRecorder(stream);
  mediaRec.ondataavailable = (e) => chunks.push(e.data);
  mediaRec.onstop = async () => {
    mic.classList.remove("rec"); stream.getTracks().forEach((t) => t.stop());
    const fd = new FormData(); fd.append("fayl", new Blob(chunks, { type: "audio/webm" }), "ovoz.webm");
    try {
      const r = await fetch("/api/ovoz/stt", { method: "POST", body: fd, headers: { "X-Admin-Token": token() } });
      const j = await r.json(); if (!r.ok) throw new Error(j.detail);
      $("#chatInput").value = j.matn; $("#chatForm").requestSubmit();
    } catch (err) { alert("Ovozni tanib bo'lmadi: " + err.message); }
  };
  mediaRec.start(); mic.classList.add("rec");
};
async function gapir(matn) {
  try {
    const r = await fetch("/api/ovoz/tts", { method: "POST", headers: { "Content-Type": "application/json", "X-Admin-Token": token() }, body: JSON.stringify({ matn }) });
    if (!r.ok) throw 0;
    new Audio(URL.createObjectURL(await r.blob())).play();
  } catch {
    const u = new SpeechSynthesisUtterance(matn);
    const v = speechSynthesis.getVoices().find((v) => v.lang.startsWith("uz")) || speechSynthesis.getVoices().find((v) => v.lang.startsWith("tr"));
    if (v) u.voice = v; u.lang = v ? v.lang : "uz-UZ"; speechSynthesis.speak(u);
  }
}

// ---------- Mijozlar ----------
async function loadMijozlar() {
  const list = await api("/api/mijozlar");
  $("#mijozRoyxat").innerHTML = list.map((m) => `<div class="card"><div class="row"><b>${esc(m.nom)}</b><span class="muted">${esc(m.telefon)}</span>
    <span class="muted" style="margin-left:auto">${m.ofislar_soni} ofis · ${m.hodimlar_soni} hodim</span></div>
    <div class="muted small">${esc(m.biznes_tavsifi)}</div>
    <div class="row" style="margin-top:8px">
      <button data-avto="${m.id}">🤖 AI jamoani o'zi tuzsin</button>
      <button data-komplekt="${m.id}">📦 Komplekt sotish</button>
      <button data-qolda="${m.id}">✋ Qo'lda tanlash</button>
      <button data-del="${m.id}" class="danger">O'chirish</button></div></div>`).join("") || `<div class="muted">Hali mijoz yo'q.</div>`;
  document.querySelectorAll("[data-avto]").forEach((b) => b.onclick = () => avtoOfis(+b.dataset.avto));
  document.querySelectorAll("[data-komplekt]").forEach((b) => b.onclick = () => komplektSot(+b.dataset.komplekt));
  document.querySelectorAll("[data-qolda]").forEach((b) => b.onclick = () => qoldaOfis(+b.dataset.qolda));
  document.querySelectorAll("[data-del]").forEach((b) => b.onclick = async () => { if (confirm("O'chirasizmi? Barcha ofislari ham o'chadi.")) { await api("/api/mijozlar/" + b.dataset.del, { method: "DELETE" }); loadMijozlar(); } });
}
$("#mijozForm").onsubmit = async (e) => {
  e.preventDefault(); const f = e.target;
  await api("/api/mijozlar", { method: "POST", body: { nom: f.nom.value, telefon: f.telefon.value, biznes_tavsifi: f.biznes_tavsifi.value } });
  f.reset(); loadMijozlar();
};
const dizaynSelect = `<select name="dizayn"><option value="klassik">🎨 Klassik</option><option value="tungi">🌙 Tungi</option><option value="yashil">🌿 Yashil</option><option value="premium">✨ Premium</option></select>`;
function goOfis(id) { ofisId = id; document.querySelector('[data-view="ofislar"]').click(); }
function avtoOfis(mid) {
  dialog(`<h3>🤖 AI HR-direktor jamoa tuzadi</h3><p class="muted">Mijozning biznes tavsifini o'qib, eng kerakli hodimlarni tanlaydi va har biriga shu biznesga mos ko'rsatma yozadi.</p>
    <label>Nechta hodim? <input name="soni" type="number" min="1" max="48" value="5"></label>${dizaynSelect}
    <div class="row"><button value="ok">Yaratish</button><button value="" class="danger">Bekor</button></div>`, async (f) => {
    const r = await api("/api/ofislar/avto", { method: "POST", body: { mijoz_id: mid, soni: +f.soni.value, dizayn: f.dizayn.value } });
    alert("Jamoa tayyor!\n\n" + (r.izoh || "") + "\n\n" + r.hodimlar.map((h) => "• " + sh(h.shablon_id).nom + " — " + h.sabab).join("\n"));
    goOfis(r.id);
  });
}
function komplektSot(mid) {
  dialog(`<h3>📦 Komplekt sotish</h3><select name="k">${Object.entries(KAT.komplektlar).map(([k, v]) => `<option value="${k}">${esc(v.nom)} — ${v.hodimlar.length} hodim, $${v.narx_oylik_usd}/oy</option>`).join("")}</select>
    ${dizaynSelect}<div class="row"><button value="ok">Ofis yaratish</button><button value="" class="danger">Bekor</button></div>`, async (f) => {
    const r = await api("/api/ofislar", { method: "POST", body: { mijoz_id: mid, nom: KAT.komplektlar[f.k.value].nom, komplekt: f.k.value, dizayn: f.dizayn.value } });
    goOfis(r.id);
  });
}
function qoldaOfis(mid) {
  dialog(`<h3>✋ Hodimlarni tanlang</h3><input name="nom" placeholder="Ofis nomi" value="Asosiy ofis">
    <div class="pick">${KAT.shablonlar.map((s) => `<label><input type="checkbox" name="s" value="${s.id}">${s.emoji} ${esc(s.nom)}</label>`).join("")}</div>
    ${dizaynSelect}<div class="row"><button value="ok">Yaratish</button><button value="" class="danger">Bekor</button></div>`, async (f) => {
    const ids = [...f.querySelectorAll('[name="s"]:checked')].map((c) => c.value);
    const r = await api("/api/ofislar", { method: "POST", body: { mijoz_id: mid, nom: f.nom.value, shablonlar: ids, dizayn: f.dizayn.value } });
    goOfis(r.id);
  });
}

// ---------- Katalog va komplektlar ----------
function renderKatalog() {
  const q = $("#qidir").value.toLowerCase();
  const list = KAT.shablonlar.filter((s) => !q || (s.nom + s.tavsif + s.konikmalar.join(" ")).toLowerCase().includes(q));
  const deps = [...new Set(list.map((s) => s.bolim))];
  $("#katalogRoyxat").innerHTML = `<p class="muted">Jami ${KAT.shablonlar.length} ta hodim shabloni. Har biri cheksiz nusxa qilib sotiladi.</p>` + deps.map((d) => `<div class="dept">${esc(d)}</div><div class="grid">` +
    list.filter((s) => s.bolim === d).map((s) => `<div class="card role" style="border-top:3px solid ${s.rang}">
      <h3>${s.emoji} ${esc(s.nom)}</h3><div class="muted small">${esc(s.tavsif)}</div>
      <div class="tags">${s.konikmalar.map((k) => `<span class="tag">${esc(k)}</span>`).join("")}</div>
      <details><summary class="small">Instruksiya (miya)</summary><pre>${esc(s.instruksiya)}</pre></details></div>`).join("") + "</div>").join("");
}
$("#qidir").oninput = renderKatalog;
function renderKomplektlar() {
  $("#komplektRoyxat").innerHTML = Object.entries(KAT.komplektlar).map(([k, v]) => `<div class="card">
    <h3>${esc(v.nom)}</h3><div class="price">$${v.narx_oylik_usd}<span class="muted small"> / oy</span></div>
    <div class="muted small">${esc(v.tavsif)} · ${KAT.ofis_hajmlari[v.ofis_hajmi].nom}</div>
    <div class="tags">${v.hodimlar.map((id) => `<span class="tag">${sh(id).emoji} ${esc(sh(id).nom)}</span>`).join("")}</div></div>`).join("");
}

// ---------- Bilim ----------
async function loadBilim() {
  const sel = $("#bilimShablon");
  if (!sel.options.length) { sel.innerHTML = KAT.shablonlar.map((s) => `<option value="${s.id}">${s.emoji} ${esc(s.nom)}</option>`).join(""); sel.onchange = loadBilim; }
  const list = await api("/api/bilimlar/" + sel.value);
  $("#bilimRoyxat").innerHTML = list.map((b) => `<div class="card"><a href="${esc(b.manba)}" target="_blank" rel="noopener">${esc(b.sarlavha)}</a>
    <div class="small muted">${esc(b.sana)}</div>${b.xulosa ? `<div>💡 ${esc(b.xulosa)}</div>` : ""}</div>`).join("") || `<div class="muted">Hali bilim yo'q. Bu shablon sotilgach yoki "Hozir yangilash" bosilgach to'planadi.</div>`;
}
$("#bilimYangila").onclick = async () => { await api("/api/bilim/yangila?barchasi=true", { method: "POST" }); alert("Yangilash boshlandi. Bir necha daqiqadan so'ng ko'ring."); };
async function bilimHolat() {
  try { const h = await api("/api/bilim/holat"); $("#bilimHolat").textContent = `🧠 Bilim: ${h.ishlayapti ? "yangilanmoqda..." : "oxirgi " + (h.oxirgi || "—")} · har ${h.interval_soat} soatda`; } catch {}
}

// ---------- Dialog yordamchisi ----------
function dialog(html, onOk) {
  const d = $("#dlg"); $("#dlgBody").innerHTML = html;
  d.onclose = async () => { if (d.returnValue === "ok") { try { await onOk($("#dlgBody")); } catch (e) { alert("Xato: " + e.message); } } };
  d.returnValue = ""; d.showModal();
}

// ---------- Start ----------
(async () => {
  KAT = await api("/api/katalog");
  Office.init($("#ofis"), openHodim);
  loadOfislar(); bilimHolat(); setInterval(bilimHolat, 30000);
})();
