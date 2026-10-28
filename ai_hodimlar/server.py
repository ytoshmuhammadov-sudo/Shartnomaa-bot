"""AI Hodimlar platformasi: admin panel API + virtual ofis.

Ishga tushirish:  uvicorn ai_hodimlar.server:app --host 0.0.0.0 --port 8000
"""

import logging
import os
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import brain, db, direktor, knowledge, telegram
from .catalog import KOMPLEKTLAR, OFIS_HAJMLARI, SHABLONLAR, ofis_hajmi_tanla

logging.basicConfig(level=logging.INFO)
STATIC = os.path.join(os.path.dirname(__file__), "static")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
_ishchilar = ThreadPoolExecutor(max_workers=int(os.getenv("VAZIFA_ISHCHILAR", "4")))


def admin(request: Request, x_admin_token: str = Header(default="")):
    if ADMIN_TOKEN and request.url.path.startswith("/api") and x_admin_token != ADMIN_TOKEN:
        raise HTTPException(401, "Admin token noto'g'ri")


app = FastAPI(title="AI Hodimlar", dependencies=[Depends(admin)])


@app.on_event("startup")
def startup():
    db.init()
    # Server qayta ishga tushganda yarim qolgan vazifalarni navbatga qaytaramiz.
    for v in db.rows("SELECT id FROM vazifalar WHERE holat IN ('yangi', 'jarayonda') AND topshiriq_id IS NULL"):
        _ishchilar.submit(brain.vazifa_bajar, v["id"])
    # Direktor topshiriqlari o'rtada uzilgan bo'lsa, qayta boshlamaymiz (guruhga takror xabar ketmasligi uchun).
    db.run("UPDATE vazifalar SET holat = 'xato', natija = 'Server qayta ishga tushdi' "
           "WHERE holat IN ('yangi', 'jarayonda') AND topshiriq_id IS NOT NULL")
    db.run("UPDATE topshiriqlar SET holat = 'uzildi' WHERE holat IN ('yangi', 'jarayonda')")
    db.run("UPDATE hodimlar SET holat = 'bosh'")
    telegram.ishga_tushir()
    if os.getenv("BILIM_YANGILASH", "1") == "1":
        knowledge.fon_ishga_tushir()


# ---------- Katalog ----------

@app.get("/api/katalog")
def katalog():
    return {"shablonlar": list(SHABLONLAR.values()), "komplektlar": KOMPLEKTLAR, "ofis_hajmlari": OFIS_HAJMLARI}


# ---------- Mijozlar va ofislar ----------

class MijozIn(BaseModel):
    nom: str
    telefon: str = ""
    biznes_tavsifi: str = ""


class OfisIn(BaseModel):
    mijoz_id: int
    nom: str
    komplekt: str | None = None          # tayyor komplekt
    shablonlar: list[str] = []           # yoki qo'lda tanlangan hodimlar
    hajm: str | None = None
    dizayn: str = "klassik"


class AvtoOfisIn(BaseModel):
    mijoz_id: int
    soni: int = 5
    dizayn: str = "klassik"


@app.get("/api/mijozlar")
def mijozlar():
    return db.rows("SELECT m.*, (SELECT COUNT(*) FROM ofislar o WHERE o.mijoz_id = m.id) AS ofislar_soni, "
                   "(SELECT COUNT(*) FROM hodimlar h JOIN ofislar o ON o.id = h.ofis_id WHERE o.mijoz_id = m.id) "
                   "AS hodimlar_soni FROM mijozlar m ORDER BY m.id DESC")


@app.post("/api/mijozlar")
def mijoz_qosh(m: MijozIn):
    return {"id": db.run("INSERT INTO mijozlar (nom, telefon, biznes_tavsifi) VALUES (?, ?, ?)",
                         m.nom, m.telefon, m.biznes_tavsifi)}


@app.delete("/api/mijozlar/{mid}")
def mijoz_ochir(mid: int):
    db.run("DELETE FROM mijozlar WHERE id = ?", mid)
    return {"ok": True}


def _yangi_kod() -> str:
    return secrets.token_hex(3).upper()


def _ofis_yarat(mijoz_id, nom, hodimlar, hajm, dizayn):
    """hodimlar: [{"shablon_id", "qoshimcha_instruksiya"}]. Har biri shablondan mustaqil nusxa."""
    if not db.one("SELECT 1 FROM mijozlar WHERE id = ?", mijoz_id):
        raise HTTPException(404, "Mijoz topilmadi")
    # Har ofisda bitta AI Direktor bo'ladi: u rahbar kabinetida o'tiradi va topshiriqlarni taqsimlaydi.
    hodimlar = [{"shablon_id": "direktor"}] + [h for h in hodimlar if h["shablon_id"] != "direktor"]
    hajm = hajm or ofis_hajmi_tanla(len(hodimlar) - 1)
    oid = db.run("INSERT INTO ofislar (mijoz_id, nom, hajm, dizayn, ulash_kodi) VALUES (?, ?, ?, ?, ?)",
                 mijoz_id, nom, hajm, dizayn, _yangi_kod())
    band = set()
    for h in hodimlar:
        if h["shablon_id"] not in SHABLONLAR:
            raise HTTPException(400, f"Noma'lum hodim: {h['shablon_id']}")
        ism = brain.tasodifiy_ism(band)
        band.add(ism)
        db.run("INSERT INTO hodimlar (ofis_id, shablon_id, ism, qoshimcha_instruksiya) VALUES (?, ?, ?, ?)",
               oid, h["shablon_id"], ism, h.get("qoshimcha_instruksiya", ""))
    return oid


@app.post("/api/ofislar")
def ofis_qosh(o: OfisIn):
    ids = KOMPLEKTLAR[o.komplekt]["hodimlar"] if o.komplekt else o.shablonlar
    if not ids:
        raise HTTPException(400, "Komplekt yoki hodimlarni tanlang")
    hajm = o.hajm or (KOMPLEKTLAR[o.komplekt]["ofis_hajmi"] if o.komplekt else None)
    oid = _ofis_yarat(o.mijoz_id, o.nom, [{"shablon_id": i} for i in ids], hajm, o.dizayn)
    return {"id": oid}


@app.post("/api/ofislar/avto")
def ofis_avto(o: AvtoOfisIn):
    """AI HR-direktor mijozning biznes tavsifiga qarab jamoani o'zi tuzadi."""
    m = db.one("SELECT * FROM mijozlar WHERE id = ?", o.mijoz_id)
    if not m:
        raise HTTPException(404, "Mijoz topilmadi")
    reja = brain.jamoa_tuz(m["biznes_tavsifi"] or m["nom"], max(1, min(o.soni, 47)))
    oid = _ofis_yarat(o.mijoz_id, f"{m['nom']} ofisi", reja["hodimlar"], None, o.dizayn)
    return {"id": oid, "izoh": reja.get("izoh", ""), "hodimlar": reja["hodimlar"]}


@app.get("/api/ofislar")
def ofislar():
    return db.rows("SELECT o.*, m.nom AS mijoz, (SELECT COUNT(*) FROM hodimlar h WHERE h.ofis_id = o.id) AS soni "
                   "FROM ofislar o JOIN mijozlar m ON m.id = o.mijoz_id ORDER BY o.id DESC")


@app.get("/api/ofislar/{oid}")
def ofis(oid: int):
    o = db.one("SELECT o.*, m.nom AS mijoz FROM ofislar o JOIN mijozlar m ON m.id = o.mijoz_id WHERE o.id = ?", oid)
    if not o:
        raise HTTPException(404, "Ofis topilmadi")
    if not o["ulash_kodi"]:
        o["ulash_kodi"] = _yangi_kod()
        db.run("UPDATE ofislar SET ulash_kodi = ? WHERE id = ?", o["ulash_kodi"], oid)
    direktor.direktori(oid)
    o["telegram"] = telegram.holat()
    o["hodimlar"] = db.rows(
        "SELECT h.*, (SELECT COUNT(*) FROM vazifalar v WHERE v.hodim_id = h.id AND v.holat = 'bajarildi') AS bajarilgan "
        "FROM hodimlar h WHERE h.ofis_id = ? ORDER BY h.id", oid)
    for h in o["hodimlar"]:
        sh = SHABLONLAR[h["shablon_id"]]
        h.update(lavozim=sh["nom"], emoji=sh["emoji"], rang=sh["rang"], bolim=sh["bolim"])
    return o


class OfisPatch(BaseModel):
    nom: str | None = None
    hajm: str | None = None
    dizayn: str | None = None


@app.patch("/api/ofislar/{oid}")
def ofis_ozgartir(oid: int, p: OfisPatch):
    for k, v in p.model_dump(exclude_none=True).items():
        db.run(f"UPDATE ofislar SET {k} = ? WHERE id = ?", v, oid)
    return {"ok": True}


@app.delete("/api/ofislar/{oid}")
def ofis_ochir(oid: int):
    db.run("DELETE FROM ofislar WHERE id = ?", oid)
    return {"ok": True}


# ---------- Hodimlar ----------

class HodimIn(BaseModel):
    ofis_id: int
    shablon_id: str
    ism: str | None = None
    qoshimcha_instruksiya: str = ""


class HodimPatch(BaseModel):
    ism: str | None = None
    qoshimcha_instruksiya: str | None = None


@app.post("/api/hodimlar")
def hodim_qosh(h: HodimIn):
    if h.shablon_id not in SHABLONLAR:
        raise HTTPException(400, "Noma'lum hodim")
    band = {r["ism"] for r in db.rows("SELECT ism FROM hodimlar WHERE ofis_id = ?", h.ofis_id)}
    return {"id": db.run("INSERT INTO hodimlar (ofis_id, shablon_id, ism, qoshimcha_instruksiya) VALUES (?, ?, ?, ?)",
                         h.ofis_id, h.shablon_id, h.ism or brain.tasodifiy_ism(band), h.qoshimcha_instruksiya)}


@app.patch("/api/hodimlar/{hid}")
def hodim_ozgartir(hid: int, p: HodimPatch):
    for k, v in p.model_dump(exclude_none=True).items():
        db.run(f"UPDATE hodimlar SET {k} = ? WHERE id = ?", v, hid)
    return {"ok": True}


@app.delete("/api/hodimlar/{hid}")
def hodim_ochir(hid: int):
    db.run("DELETE FROM hodimlar WHERE id = ?", hid)
    return {"ok": True}


class XabarIn(BaseModel):
    matn: str


@app.get("/api/hodimlar/{hid}/xabarlar")
def xabarlar(hid: int):
    return db.rows("SELECT * FROM xabarlar WHERE hodim_id = ? ORDER BY id DESC LIMIT 50", hid)[::-1]


@app.post("/api/hodimlar/{hid}/suhbat")
def suhbat(hid: int, x: XabarIn):
    if not db.one("SELECT 1 FROM hodimlar WHERE id = ?", hid):
        raise HTTPException(404, "Hodim topilmadi")
    return {"javob": brain.suhbat(hid, x.matn)}


@app.get("/api/hodimlar/{hid}/vazifalar")
def vazifalar(hid: int):
    return db.rows("SELECT * FROM vazifalar WHERE hodim_id = ? ORDER BY id DESC LIMIT 50", hid)


@app.post("/api/hodimlar/{hid}/vazifalar")
def vazifa_ber(hid: int, x: XabarIn):
    vid = db.run("INSERT INTO vazifalar (hodim_id, matn) VALUES (?, ?)", hid, x.matn)
    _ishchilar.submit(brain.vazifa_bajar, vid)
    return {"id": vid}


# ---------- Direktor topshiriqlari ----------

@app.post("/api/ofislar/{oid}/topshiriq")
def topshiriq_ber(oid: int, x: XabarIn):
    o = db.one("SELECT * FROM ofislar WHERE id = ?", oid)
    if not o:
        raise HTTPException(404, "Ofis topilmadi")
    tid = db.run("INSERT INTO topshiriqlar (ofis_id, matn, chat_id) VALUES (?, ?, ?)", oid, x.matn, o["telegram_chat_id"])
    _ishchilar.submit(direktor.ishla, tid)
    return {"id": tid}


@app.get("/api/ofislar/{oid}/topshiriqlar")
def topshiriqlar(oid: int):
    ts = db.rows("SELECT * FROM topshiriqlar WHERE ofis_id = ? ORDER BY id DESC LIMIT 20", oid)
    for t in ts:
        t["vazifalar"] = db.rows("SELECT v.*, h.ism, h.shablon_id FROM vazifalar v JOIN hodimlar h ON h.id = v.hodim_id "
                                 "WHERE v.topshiriq_id = ? ORDER BY v.id", t["id"])
    return ts


# ---------- Bilim bazasi ----------

@app.get("/api/bilimlar/{shablon_id}")
def bilimlar(shablon_id: str):
    return db.rows("SELECT * FROM bilimlar WHERE shablon_id = ? ORDER BY sana DESC LIMIT 50", shablon_id)


@app.get("/api/bilim/holat")
def bilim_holat():
    return knowledge.holat()


@app.post("/api/bilim/yangila")
def bilim_yangila(barchasi: bool = False):
    threading.Thread(target=knowledge.hammasini_yangila, args=(not barchasi,), daemon=True).start()
    return {"ok": True}


# ---------- Ovoz (o'zbekcha golos) ----------

@app.post("/api/ovoz/stt")
async def ovoz_matnga(fayl: UploadFile):
    """Ovozli xabarni matnga aylantiradi (Whisper, uzbek tili). Brauzer uz-UZ tanimasa ishlatiladi."""
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(501, "OPENAI_API_KEY o'rnatilmagan: brauzer ovoz tanish funksiyasidan foydalaning")
    from openai import OpenAI
    data = await fayl.read()
    t = OpenAI().audio.transcriptions.create(model="whisper-1", file=(fayl.filename or "ovoz.webm", data), language="uz")
    return {"matn": t.text}


@app.post("/api/ovoz/tts")
def matn_ovozga(x: XabarIn):
    """Javobni o'zbekcha ovozga aylantiradi."""
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(501, "OPENAI_API_KEY o'rnatilmagan")
    from openai import OpenAI
    audio = OpenAI().audio.speech.create(model=os.getenv("TTS_MODEL", "gpt-4o-mini-tts"), voice="alloy",
                                         input=x.matn[:4000], instructions="Speak in Uzbek, natural and friendly.")
    return Response(audio.read(), media_type="audio/mpeg")


# ---------- Frontend ----------

@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC), name="static")
