"""AI hodimlarning "miyasi": Claude bilan suhbat, vazifa bajarish, jamoa tuzish."""

import json
import logging
import os
import random

import anthropic

from . import db
from .catalog import SHABLONLAR, UMUMIY_QOIDALAR

log = logging.getLogger("ai_hodimlar.brain")

MODEL = os.getenv("AI_HODIM_MODEL", "claude-opus-5-5")
# Yangiliklarni qisqartirish uchun arzon model (ommaviy ish).
SUMMARY_MODEL = os.getenv("AI_BILIM_MODEL", "claude-haiku-5-5")
FALLBACK_BETA = "server-side-fallback-2026-07-01"

ISMLAR = ["Aziz", "Dilnoza", "Jasur", "Malika", "Bekzod", "Nilufar", "Sardor", "Madina", "Otabek", "Shahnoza",
          "Javohir", "Kamola", "Rustam", "Zarina", "Timur", "Gulnoza", "Islom", "Sevara", "Akmal", "Feruza",
          "Doniyor", "Laylo", "Sherzod", "Mohira", "Ulug'bek", "Nodira", "Behruz", "Iroda", "Farrux", "Durdona"]

_client = None


def client():
    """Kalit bo'lmasa None qaytaradi: platforma demo rejimda ishlaydi."""
    global _client
    if _client is None and (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")):
        _client = anthropic.Anthropic()
    return _client


def tasodifiy_ism(band: set) -> str:
    bosh = [i for i in ISMLAR if i not in band]
    return random.choice(bosh or ISMLAR)


def system_prompt(hodim: dict) -> list:
    sh = SHABLONLAR[hodim["shablon_id"]]
    ofis = db.one("SELECT o.*, m.nom AS mijoz, m.biznes_tavsifi FROM ofislar o JOIN mijozlar m ON m.id = o.mijoz_id "
                  "WHERE o.id = ?", hodim["ofis_id"])
    hamkasblar = db.rows("SELECT ism, shablon_id FROM hodimlar WHERE ofis_id = ? AND id != ?",
                         hodim["ofis_id"], hodim["id"])
    stable = UMUMIY_QOIDALAR.format(kompaniya=ofis["mijoz"], ism=hodim["ism"], lavozim=sh["nom"])
    stable += f"\nLavozim bo'yicha ko'rsatma:\n{sh['instruksiya']}\n"
    stable += "Ko'nikmalaring: " + ", ".join(sh["konikmalar"]) + "\n"
    if ofis["biznes_tavsifi"]:
        stable += f"\nKompaniya haqida: {ofis['biznes_tavsifi']}\n"
    if hamkasblar:
        stable += "Hamkasblaring: " + ", ".join(
            f"{h['ism']} ({SHABLONLAR[h['shablon_id']]['nom']})" for h in hamkasblar) + "\n"
    if hodim.get("qoshimcha_instruksiya"):
        stable += f"\nRahbarning maxsus ko'rsatmasi:\n{hodim['qoshimcha_instruksiya']}\n"

    bilim = db.rows("SELECT sarlavha, xulosa, sana FROM bilimlar WHERE shablon_id = ? ORDER BY sana DESC LIMIT 10",
                    hodim["shablon_id"])
    blocks = [{"type": "text", "text": stable, "cache_control": {"type": "ephemeral"}}]
    if bilim:
        fresh = "So'nggi soha yangiliklari (bilim bazang, 24/7 yangilanadi):\n" + "\n".join(
            f"- [{b['sana'][:10]}] {b['sarlavha']}" + (f" — {b['xulosa']}" if b["xulosa"] else "") for b in bilim)
        blocks.append({"type": "text", "text": fresh})
    return blocks


def _ask(system, messages, effort="medium", web=True, max_tokens=16000) -> str:
    c = client()
    if c is None:
        last = messages[-1]["content"] if messages else ""
        return ("(Demo rejim: ANTHROPIC_API_KEY o'rnatilmagan.) Topshiriqni qabul qildim: "
                f"\"{str(last)[:200]}\". Kalit qo'shilgach, to'liq javob beraman.")
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}] if web else []
    msgs = list(messages)
    parts = []
    for _ in range(4):  # pause_turn bo'lsa davom ettiramiz
        try:
            resp = c.beta.messages.create(
                model=MODEL, max_tokens=max_tokens, system=system, messages=msgs, tools=tools,
                output_config={"effort": effort},
                betas=[FALLBACK_BETA], fallbacks="default",
            )
        except anthropic.RateLimitError:
            return "Hozir so'rovlar ko'p, birozdan keyin qayta urinib ko'ring."
        except anthropic.APIStatusError as e:
            log.exception("Claude API xatosi")
            return f"AI xizmatida xato ({e.status_code}). Administratorga xabar bering."
        except anthropic.APIConnectionError:
            return "AI xizmatiga ulanib bo'lmadi. Internetni tekshiring."
        if resp.stop_reason == "refusal":
            return "Bu so'rovni bajara olmayman. Iltimos, boshqacha shakllantiring."
        parts += [b.text for b in resp.content if b.type == "text"]
        if resp.stop_reason != "pause_turn":
            break
        msgs = msgs + [{"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in resp.content]}]
    return "".join(parts).strip() or "(bo'sh javob)"


def suhbat(hodim_id: int, matn: str) -> str:
    hodim = db.one("SELECT * FROM hodimlar WHERE id = ?", hodim_id)
    tarix = db.rows("SELECT rol, matn FROM xabarlar WHERE hodim_id = ? ORDER BY id DESC LIMIT 20", hodim_id)[::-1]
    messages = [{"role": r["rol"], "content": r["matn"]} for r in tarix] + [{"role": "user", "content": matn}]
    db.run("UPDATE hodimlar SET holat = 'suhbatda' WHERE id = ?", hodim_id)
    javob = _ask(system_prompt(hodim), messages, effort="medium")
    db.run("INSERT INTO xabarlar (hodim_id, rol, matn) VALUES (?, 'user', ?)", hodim_id, matn)
    db.run("INSERT INTO xabarlar (hodim_id, rol, matn) VALUES (?, 'assistant', ?)", hodim_id, javob)
    db.run("UPDATE hodimlar SET holat = 'bosh' WHERE id = ?", hodim_id)
    return javob


def vazifa_bajar(vazifa_id: int):
    v = db.one("SELECT * FROM vazifalar WHERE id = ?", vazifa_id)
    hodim = db.one("SELECT * FROM hodimlar WHERE id = ?", v["hodim_id"])
    db.run("UPDATE vazifalar SET holat = 'jarayonda' WHERE id = ?", vazifa_id)
    db.run("UPDATE hodimlar SET holat = 'ishlayapti' WHERE id = ?", hodim["id"])
    try:
        prompt = ("Rahbardan yangi vazifa keldi. Uni to'liq bajar va tayyor natijani ber "
                  "(matn, jadval yoki reja ko'rinishida, darhol ishlatsa bo'ladigan holda).\n\nVazifa: " + v["matn"])
        natija = _ask(system_prompt(hodim), [{"role": "user", "content": prompt}], effort="high")
        db.run("UPDATE vazifalar SET holat = 'bajarildi', natija = ?, done = CURRENT_TIMESTAMP WHERE id = ?",
               natija, vazifa_id)
    except Exception as e:  # vazifa navbati to'xtab qolmasligi uchun
        log.exception("Vazifa bajarilmadi")
        db.run("UPDATE vazifalar SET holat = 'xato', natija = ? WHERE id = ?", str(e), vazifa_id)
    finally:
        db.run("UPDATE hodimlar SET holat = 'bosh' WHERE id = ?", hodim["id"])


JAMOA_SCHEMA = {
    "type": "object",
    "properties": {
        "izoh": {"type": "string"},
        "hodimlar": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "shablon_id": {"type": "string", "enum": list(SHABLONLAR)},
                    "sabab": {"type": "string"},
                    "qoshimcha_instruksiya": {"type": "string"},
                },
                "required": ["shablon_id", "sabab", "qoshimcha_instruksiya"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["izoh", "hodimlar"],
    "additionalProperties": False,
}


def jamoa_tuz(biznes_tavsifi: str, soni: int) -> dict:
    """HR-direktor AI: biznes tavsifiga qarab kerakli hodimlarni tanlaydi va sozlaydi."""
    c = client()
    if c is None:
        return _jamoa_offline(biznes_tavsifi, soni)
    katalog = "\n".join(f"- {k}: {v['nom']} ({v['bolim']}) — {v['tavsif']}" for k, v in SHABLONLAR.items())
    resp = c.messages.create(
        model=MODEL, max_tokens=16000,
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": JAMOA_SCHEMA}},
        system="Sen AI hodimlar platformasining HR-direktorisan. Biznesga eng ko'p foyda keltiradigan AI hodimlar "
               "jamoasini katalogdan tanlaysan va har biriga shu biznesga moslashtirilgan qo'shimcha ko'rsatma yozasan. "
               "Hammasini o'zbek tilida (lotin) yoz.",
        messages=[{"role": "user", "content":
                   f"Katalog:\n{katalog}\n\nBiznes: {biznes_tavsifi}\nKerakli hodimlar soni: {soni}. "
                   "Eng muhimidan boshlab tartibla, takrorlama."}],
    )
    if resp.stop_reason == "refusal":
        return _jamoa_offline(biznes_tavsifi, soni)
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    data = json.loads(text)
    seen, out = set(), []
    for h in data.get("hodimlar", []):
        if h["shablon_id"] in SHABLONLAR and h["shablon_id"] not in seen:
            seen.add(h["shablon_id"])
            out.append(h)
    data["hodimlar"] = out[:soni]
    return data


_KALITLAR = {
    "marketplace_menejer": ["uzum", "wildberries", "ozon", "marketplace"],
    "restoran_menejer": ["restoran", "kafe", "oshxona", "fastfud"],
    "klinika_admin": ["klinika", "shifoxona", "stomatolog", "tibbiy"],
    "talim_metodist": ["o'quv", "kurs", "maktab", "ta'lim", "akademiya"],
    "kochmas_mulk_agent": ["ko'chmas", "kvartira", "uy-joy", "qurilish", "rieltor"],
    "turizm_menejer": ["turizm", "sayohat", "tur", "viza"],
    "dasturchi": ["it", "dastur", "startap", "saas"],
    "logistika": ["ombor", "yetkazib", "logistika", "dokon", "do'kon"],
    "yurist": ["shartnoma", "yuridik"],
}
_ASOSIY = ["sotuv_menejeri", "dm_sotuvchi", "smm_menejer", "support_operator", "ijrochi_yordamchi", "kopirayter",
           "target_mutaxassis", "buxgalter", "crm_menejer", "hr_rekruter", "loyiha_menejeri", "bozor_tadqiqotchi",
           "moliyaviy_tahlilchi", "video_ssenarist", "yurist", "retention_menejer", "biznes_analitik", "seo_mutaxassis",
           "call_operator", "ui_dizayner"]


def _jamoa_offline(biznes_tavsifi: str, soni: int) -> dict:
    t = biznes_tavsifi.lower()
    tanlov = [k for k, words in _KALITLAR.items() if any(w in t for w in words)]
    tanlov += [k for k in _ASOSIY if k not in tanlov]
    return {
        "izoh": "Kalit so'zlar bo'yicha tanlandi (demo rejim).",
        "hodimlar": [{"shablon_id": k, "sabab": SHABLONLAR[k]["tavsif"], "qoshimcha_instruksiya": ""}
                     for k in tanlov[:soni]],
    }


def bilim_xulosa(shablon_id: str, sarlavhalar: list[str]) -> list[str]:
    """Yangiliklar sarlavhalarini rol uchun 1 qatorlik o'zbekcha xulosaga aylantiradi."""
    c = client()
    if c is None or not sarlavhalar:
        return [""] * len(sarlavhalar)
    sh = SHABLONLAR[shablon_id]
    schema = {"type": "object", "properties": {"xulosalar": {"type": "array", "items": {"type": "string"}}},
              "required": ["xulosalar"], "additionalProperties": False}
    try:
        resp = c.messages.create(
            model=SUMMARY_MODEL, max_tokens=4000,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content":
                       f"Sen {sh['nom']} uchun yangiliklarni saralaysan. Har sarlavha uchun o'zbek tilida bitta qisqa gap yoz: "
                       "bu yangilik shu lavozimdagi hodim ishiga qanday ta'sir qiladi. Aloqasi bo'lmasa, bo'sh satr qaytar. "
                       "Tartibni saqla.\n\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(sarlavhalar))}],
        )
        text = next((b.text for b in resp.content if b.type == "text"), "{}")
        xul = json.loads(text).get("xulosalar", [])
    except (anthropic.APIError, json.JSONDecodeError):
        log.exception("Bilim xulosasi olinmadi")
        xul = []
    return (xul + [""] * len(sarlavhalar))[:len(sarlavhalar)]
