"""Bilim bazasini 24/7 yangilash: har bir rol uchun yangiliklar oqimini o'qib, xulosalab saqlaydi.

Bilim shablon darajasida saqlanadi, shuning uchun bitta yangilanish shu shablondan
olingan barcha mijozlardagi hodimlarga birdaniga yetib boradi.
"""

import logging
import os
import threading
import time

import feedparser

from . import brain, db
from .catalog import SHABLONLAR

log = logging.getLogger("ai_hodimlar.knowledge")

INTERVAL_SOAT = float(os.getenv("BILIM_INTERVAL_SOAT", "6"))
HAR_MANBADAN = 6
_holat = {"oxirgi": None, "ishlayapti": False}


def yangila(shablon_id: str) -> int:
    sh = SHABLONLAR[shablon_id]
    yangi = []
    for url in sh["manbalar"]:
        try:
            feed = feedparser.parse(url)
        except Exception:
            log.exception("RSS o'qilmadi: %s", url)
            continue
        for e in feed.entries[:HAR_MANBADAN]:
            link = e.get("link")
            if link and not db.one("SELECT 1 FROM bilimlar WHERE shablon_id = ? AND manba = ?", shablon_id, link):
                yangi.append((e.get("title", "").strip(), link))
    if not yangi:
        return 0
    xulosalar = brain.bilim_xulosa(shablon_id, [t for t, _ in yangi])
    for (title, link), xul in zip(yangi, xulosalar):
        db.run("INSERT OR IGNORE INTO bilimlar (shablon_id, sarlavha, xulosa, manba) VALUES (?, ?, ?, ?)",
               shablon_id, title, xul, link)
    # Bilim bazasi cheksiz o'smasin: har rol uchun oxirgi 200 tasini saqlaymiz.
    db.run("DELETE FROM bilimlar WHERE shablon_id = ? AND id NOT IN "
           "(SELECT id FROM bilimlar WHERE shablon_id = ? ORDER BY sana DESC LIMIT 200)", shablon_id, shablon_id)
    return len(yangi)


def hammasini_yangila(faqat_faollar: bool = True) -> dict:
    """faqat_faollar=True bo'lsa, faqat sotilgan (ishlatilayotgan) shablonlar yangilanadi - API tejash uchun."""
    _holat["ishlayapti"] = True
    try:
        ids = list(SHABLONLAR)
        if faqat_faollar:
            faol = {r["shablon_id"] for r in db.rows("SELECT DISTINCT shablon_id FROM hodimlar")}
            ids = [i for i in ids if i in faol]
        natija = {i: yangila(i) for i in ids}
        _holat["oxirgi"] = time.strftime("%Y-%m-%d %H:%M")
        return natija
    finally:
        _holat["ishlayapti"] = False


def holat():
    return dict(_holat, interval_soat=INTERVAL_SOAT)


def fon_ishga_tushir():
    def loop():
        while True:
            try:
                hammasini_yangila()
            except Exception:
                log.exception("Bilim yangilashda xato")
            time.sleep(INTERVAL_SOAT * 3600)

    threading.Thread(target=loop, daemon=True, name="bilim-yangilovchi").start()
