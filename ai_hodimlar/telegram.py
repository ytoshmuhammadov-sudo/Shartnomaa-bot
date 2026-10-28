"""Telegram: ofis jamoasi biznesmen guruhida ishlaydi.

Biznesmen botni guruhga qo'shadi va `/ulash KOD` yozadi (kod admin panelda). Shundan keyin:
- oddiy xabar yoki ovozli xabar -> AI Direktorga topshiriq; direktor jamoaga taqsimlaydi, natijalar guruhga yoziladi;
- "Ism, ..." bilan boshlangan xabar -> to'g'ridan-to'g'ri shu hodimga.
Bot guruhdagi barcha xabarlarni ko'rishi uchun uni guruh admini qiling (yoki BotFather'da /setprivacy -> Disable).
"""

import json
import logging
import os
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import brain, db, direktor

log = logging.getLogger("ai_hodimlar.telegram")
TOKEN = os.getenv("AI_HODIM_BOT_TOKEN", "")
_pool = ThreadPoolExecutor(max_workers=int(os.getenv("TELEGRAM_ISHCHILAR", "8")))
_bot = {"username": ""}

YORDAM = """🤖 AI Hodimlar boti

1. Meni guruhingizga qo'shing va admin qiling.
2. Admin paneldagi ofis kodini yuboring: /ulash KOD
3. Direktorga topshiriq yozing yoki ovozli xabar yuboring — u jamoaga taqsimlaydi.
4. Aniq hodimga murojaat: "Aziz, ertangi post uchun 3 ta g'oya ber"

Buyruqlar: /jamoa — hodimlar ro'yxati, /hisobot — oxirgi topshiriqlar holati."""


def _call(method: str, **params):
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/{method}",
                                 data=json.dumps(params).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=params.get("timeout", 0) + 15) as r:
        return json.loads(r.read())["result"]


def yubor(chat_id, matn: str):
    if not TOKEN or not chat_id:
        return
    for i in range(0, len(matn), 4000):  # Telegram cheklovi 4096 belgi
        try:
            _call("sendMessage", chat_id=chat_id, text=matn[i:i + 4000])
        except Exception:
            log.exception("Telegramga yuborilmadi")


def _ovoz_matnga(file_id: str) -> str | None:
    if not os.getenv("OPENAI_API_KEY"):
        return None
    from openai import OpenAI
    path = _call("getFile", file_id=file_id)["file_path"]
    with urllib.request.urlopen(f"https://api.telegram.org/file/bot{TOKEN}/{path}", timeout=60) as r:
        data = r.read()
    return OpenAI().audio.transcriptions.create(model="whisper-1", file=("ovoz.ogg", data), language="uz").text


def _jamoa_matni(ofis_id: int) -> str:
    hs = db.rows("SELECT * FROM hodimlar WHERE ofis_id = ? ORDER BY shablon_id != 'direktor', id", ofis_id)
    return "\n".join(direktor.imzo(h) for h in hs)


def _handle(upd: dict):
    msg = upd.get("message")
    if not msg:
        return
    chat_id = str(msg["chat"]["id"])
    private = msg["chat"]["type"] == "private"
    matn = (msg.get("text") or msg.get("caption") or "").strip()
    ofis = db.one("SELECT * FROM ofislar WHERE telegram_chat_id = ?", chat_id)

    if matn.startswith("/"):
        buyruq, _, arg = matn.partition(" ")
        buyruq = buyruq.split("@")[0].lower()
        if buyruq in ("/start", "/yordam", "/help"):
            return yubor(chat_id, YORDAM)
        if buyruq == "/ulash":
            o = db.one("SELECT * FROM ofislar WHERE ulash_kodi = ?", arg.strip().upper())
            if not o:
                return yubor(chat_id, "❌ Kod topilmadi. Admin paneldagi ofis kodini tekshiring.")
            db.run("UPDATE ofislar SET telegram_chat_id = ? WHERE id = ?", chat_id, o["id"])
            d = direktor.direktori(o["id"])
            return yubor(chat_id, f"✅ \"{o['nom']}\" ofisi ulandi!\n\nJamoa:\n{_jamoa_matni(o['id'])}\n\n"
                                  f"{direktor.imzo(d)}: Assalomu alaykum! Topshiriqlaringizni kutaman.")
        if not ofis:
            return yubor(chat_id, "Avval ofisni ulang: /ulash KOD")
        if buyruq == "/jamoa":
            return yubor(chat_id, _jamoa_matni(ofis["id"]))
        if buyruq == "/hisobot":
            ts = db.rows("SELECT * FROM topshiriqlar WHERE ofis_id = ? ORDER BY id DESC LIMIT 5", ofis["id"])
            belgi = {"yangi": "⏳", "jarayonda": "⚙️", "bajarildi": "✅", "xato": "❌", "uzildi": "⛔"}
            return yubor(chat_id, "\n".join(f"{belgi.get(t['holat'], '•')} {t['matn'][:80]}" for t in ts)
                         or "Hali topshiriq yo'q.")
        return

    if not ofis:
        if private:
            yubor(chat_id, YORDAM)
        return
    if msg.get("voice") or msg.get("audio"):
        try:
            matn = _ovoz_matnga((msg.get("voice") or msg.get("audio"))["file_id"])
        except Exception:
            log.exception("Ovoz tanilmadi")
            matn = None
        if not matn:
            return yubor(chat_id, "🎤 Ovozli xabarni tanish uchun serverga OPENAI_API_KEY qo'shilishi kerak.")
        yubor(chat_id, f"🎤 Eshitdim: {matn}")
    if not matn:
        return
    if _bot["username"]:
        matn = re.sub(rf"@{re.escape(_bot['username'])}\b", "", matn, flags=re.I).strip()

    # "Aziz, ..." -> to'g'ridan-to'g'ri hodimga
    for h in db.rows("SELECT * FROM hodimlar WHERE ofis_id = ? AND shablon_id != 'direktor'", ofis["id"]):
        m = re.match(rf"@?{re.escape(h['ism'])}\b[\s,:!-]*(.*)", matn, flags=re.I | re.S)
        if m and m.group(1).strip():
            _call("sendChatAction", chat_id=chat_id, action="typing")
            return yubor(chat_id, f"{direktor.imzo(h)}:\n{brain.suhbat(h['id'], m.group(1).strip())}")

    # Qolgan hammasi -> direktorga
    _call("sendChatAction", chat_id=chat_id, action="typing")
    tid = db.run("INSERT INTO topshiriqlar (ofis_id, matn, chat_id) VALUES (?, ?, ?)", ofis["id"], matn, chat_id)
    direktor.ishla(tid)


def _safe(upd):
    try:
        _handle(upd)
    except Exception:
        log.exception("Telegram xabarini qayta ishlashda xato")


def ishga_tushir():
    """Long-polling: alohida jarayon kerak emas, server bilan birga ishlaydi (bitta uvicorn worker)."""
    if not TOKEN:
        log.info("AI_HODIM_BOT_TOKEN yo'q: Telegram o'chirilgan")
        return

    def loop():
        offset = 0
        while True:
            try:
                if not _bot["username"]:
                    _bot["username"] = _call("getMe")["username"]
                for upd in _call("getUpdates", offset=offset, timeout=50, allowed_updates=["message"]):
                    offset = upd["update_id"] + 1
                    _pool.submit(_safe, upd)
            except Exception:
                log.exception("Telegram polling xatosi")
                time.sleep(5)

    threading.Thread(target=loop, daemon=True, name="telegram").start()


def holat() -> dict:
    return {"yoqilgan": bool(TOKEN), "bot": _bot["username"]}

