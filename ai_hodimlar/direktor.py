"""AI Direktor: biznesmen topshirig'ini jamoaga taqsimlaydi, natijalarni yig'ib hisobot beradi.

Oqim: topshiriq -> direktor reja tuzadi (kim, nima, qaysi bosqichda) -> har bosqich parallel bajariladi,
keyingi bosqich oldingi natijalarni ko'radi -> direktor yakuniy hisobot yozadi.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor

from . import brain, db
from .catalog import SHABLONLAR

log = logging.getLogger("ai_hodimlar.direktor")

REJA_SCHEMA = {
    "type": "object",
    "properties": {
        "javob": {"type": "string"},
        "vazifalar": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "hodim_id": {"type": "integer"},
                    "bosqich": {"type": "integer"},
                    "vazifa": {"type": "string"},
                },
                "required": ["hodim_id", "bosqich", "vazifa"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["javob", "vazifalar"],
    "additionalProperties": False,
}


def direktori(ofis_id: int) -> dict:
    """Ofis direktorini qaytaradi; eski ofislarda bo'lmasa yaratadi."""
    d = db.one("SELECT * FROM hodimlar WHERE ofis_id = ? AND shablon_id = 'direktor' ORDER BY id LIMIT 1", ofis_id)
    if not d:
        band = {r["ism"] for r in db.rows("SELECT ism FROM hodimlar WHERE ofis_id = ?", ofis_id)}
        hid = db.run("INSERT INTO hodimlar (ofis_id, shablon_id, ism) VALUES (?, 'direktor', ?)",
                     ofis_id, brain.tasodifiy_ism(band))
        d = db.one("SELECT * FROM hodimlar WHERE id = ?", hid)
    return d


def imzo(h: dict) -> str:
    sh = SHABLONLAR[h["shablon_id"]]
    return f"{sh['emoji']} {h['ism']} ({sh['nom']})"


def _jamoa(ofis_id: int) -> list[dict]:
    return db.rows("SELECT * FROM hodimlar WHERE ofis_id = ? AND shablon_id != 'direktor' ORDER BY id", ofis_id)


def rejala(direktor: dict, matn: str) -> dict:
    jamoa = _jamoa(direktor["ofis_id"])
    c = brain.client()
    if c is None:
        return _reja_offline(jamoa, matn)
    royxat = "\n".join(f"- id={h['id']}: {h['ism']} — {SHABLONLAR[h['shablon_id']]['nom']} "
                       f"({SHABLONLAR[h['shablon_id']]['tavsif']})" for h in jamoa)
    tarix = db.rows("SELECT rol, matn FROM xabarlar WHERE hodim_id = ? ORDER BY id DESC LIMIT 6", direktor["id"])[::-1]
    oldingi = "\n".join(f"{'Egasi' if r['rol'] == 'user' else 'Sen'}: {r['matn'][:500]}" for r in tarix)
    resp = c.messages.create(
        model=brain.MODEL, max_tokens=16000,
        system=brain.system_prompt(direktor),
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": REJA_SCHEMA}},
        messages=[{"role": "user", "content":
                   f"Jamoang:\n{royxat}\n\n" + (f"Oldingi suhbat:\n{oldingi}\n\n" if oldingi else "") +
                   f"Egasidan yangi xabar: {matn}\n\n"
                   "Agar bu oddiy savol yoki salomlashish bo'lsa, `javob`ga o'zing javob yoz va `vazifalar`ni bo'sh qoldir. "
                   "Agar ish bo'lsa, `javob`ga egasiga qisqa tasdiq yoz (nima qilinishini) va `vazifalar`ga har bir hodimga "
                   "aniq, mustaqil bajariladigan vazifa yoz. `bosqich` 1 dan boshlanadi; keyingi bosqich oldingi natijalarni ko'radi. "
                   "Faqat kerakli hodimlarni jalb qil, faqat yuqoridagi id'lardan foydalan."}],
    )
    if resp.stop_reason == "refusal":
        return {"javob": "Bu topshiriqni bajara olmaymiz. Iltimos, boshqacha shakllantiring.", "vazifalar": []}
    reja = json.loads(next((b.text for b in resp.content if b.type == "text"), "{}"))
    ids = {h["id"] for h in jamoa}
    reja["vazifalar"] = [v for v in reja.get("vazifalar", []) if v["hodim_id"] in ids]
    return reja


def _reja_offline(jamoa, matn):
    if not jamoa or (len(matn) < 40 and matn.rstrip().endswith("?")):
        return {"javob": "(Demo rejim) Savolingizni qabul qildim. ANTHROPIC_API_KEY qo'shilgach to'liq javob beraman.",
                "vazifalar": []}
    return {"javob": "(Demo rejim) Topshiriqni jamoaga taqsimladim.",
            "vazifalar": [{"hodim_id": h["id"], "bosqich": 1, "vazifa": matn} for h in jamoa[:3]]}


def ishla(topshiriq_id: int, xabar=None):
    """Topshiriqni boshidan oxirigacha bajaradi. xabar(matn) — jarayonni guruhga yozib borish uchun."""
    t = db.one("SELECT * FROM topshiriqlar WHERE id = ?", topshiriq_id)
    if xabar is None:
        from . import telegram
        xabar = (lambda m: telegram.yubor(t["chat_id"], m)) if t["chat_id"] else (lambda m: None)
    d = direktori(t["ofis_id"])
    db.run("UPDATE topshiriqlar SET holat = 'jarayonda' WHERE id = ?", topshiriq_id)
    db.run("UPDATE hodimlar SET holat = 'ishlayapti' WHERE id = ?", d["id"])
    try:
        reja = rejala(d, t["matn"])
        db.run("UPDATE topshiriqlar SET reja = ? WHERE id = ?", json.dumps(reja, ensure_ascii=False), topshiriq_id)
        if not reja["vazifalar"]:
            hisobot = reja["javob"]
            xabar(f"{imzo(d)}:\n{hisobot}")
        else:
            hodimlar = {h["id"]: h for h in _jamoa(t["ofis_id"])}
            bosqichlar = sorted({v["bosqich"] for v in reja["vazifalar"]})
            reja_matn = "\n".join(
                f"{b}-bosqich:\n" + "\n".join(f"  • {imzo(hodimlar[v['hodim_id']])} — {v['vazifa']}"
                                              for v in reja["vazifalar"] if v["bosqich"] == b) for b in bosqichlar)
            xabar(f"{imzo(d)}:\n{reja['javob']}\n\n📋 Reja:\n{reja_matn}")
            natijalar = []
            for b in bosqichlar:
                kontekst = "\n\n".join(f"{n['kim']}:\n{n['natija'][:3000]}" for n in natijalar)
                vids = [(db.run("INSERT INTO vazifalar (hodim_id, matn, topshiriq_id) VALUES (?, ?, ?)",
                                v["hodim_id"], v["vazifa"], topshiriq_id), hodimlar[v["hodim_id"]])
                        for v in reja["vazifalar"] if v["bosqich"] == b]
                with ThreadPoolExecutor(max_workers=4) as pool:
                    list(pool.map(lambda p: brain.vazifa_bajar(p[0], kontekst), vids))
                for vid, h in vids:
                    natija = db.one("SELECT natija FROM vazifalar WHERE id = ?", vid)["natija"]
                    natijalar.append({"kim": imzo(h), "natija": natija})
                    xabar(f"{imzo(h)} — ✅ bajarildi:\n\n{natija}")
            db.run("UPDATE hodimlar SET holat = 'ishlayapti' WHERE id = ?", d["id"])
            hisobot = brain._ask(
                brain.system_prompt(d),
                [{"role": "user", "content": f"Egasining topshirig'i: {t['matn']}\n\nJamoa natijalari:\n\n" +
                  "\n\n".join(f"{n['kim']}:\n{n['natija']}" for n in natijalar) +
                  "\n\nEgasiga yakuniy hisobot yoz: nima qilindi, eng muhim natijalar, egasidan kerak bo'lgan qarorlar."}],
                effort="medium", web=False)
            xabar(f"{imzo(d)} — 📊 yakuniy hisobot:\n\n{hisobot}")
        db.run("UPDATE topshiriqlar SET holat = 'bajarildi', hisobot = ?, done = CURRENT_TIMESTAMP WHERE id = ?",
               hisobot, topshiriq_id)
        db.run("INSERT INTO xabarlar (hodim_id, rol, matn) VALUES (?, 'user', ?)", d["id"], t["matn"])
        db.run("INSERT INTO xabarlar (hodim_id, rol, matn) VALUES (?, 'assistant', ?)", d["id"], hisobot)
    except Exception as e:
        log.exception("Direktor topshiriqni bajara olmadi")
        db.run("UPDATE topshiriqlar SET holat = 'xato', hisobot = ? WHERE id = ?", str(e), topshiriq_id)
        xabar(f"{imzo(d)}: ⚠️ topshiriqni bajarishda xato yuz berdi. Administratorga xabar berildi.")
    finally:
        db.run("UPDATE hodimlar SET holat = 'bosh' WHERE id = ?", d["id"])
