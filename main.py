import os
import asyncio
import logging
import tempfile
from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from openai import AsyncOpenAI
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

# Environment o'zgaruvchilaridan tokenlarni olish
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Kompaniya rekvizitlari (bir nechta qator bo'lishi mumkin, "\n" bilan)
REKVIZITLAR = os.getenv("REKVIZITLAR", "").replace("\\n", "\n")
DIREKTOR = "Bobur Mirzo Yo'ldoshboyev"

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN environment o'zgaruvchisi o'rnatilmagan!")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Kirill va o'zbek harflarini to'g'ri ko'rsatish uchun Unicode shrift
FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(FONTS_DIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join(FONTS_DIR, "DejaVuSans-Bold.ttf")))


class XodimForm(StatesGroup):
    xodim_info = State()
    loyixa_info = State()
    oylik_info = State()
    kpi_info = State()


class HamkorForm(StatesGroup):
    hamkor_info = State()
    predmet_info = State()
    tolov_info = State()
    muddat_info = State()


main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Xodim Shartnomasi"), KeyboardButton(text="🤝 Hamkor Shartnomasi")],
        [KeyboardButton(text="🏢 Kompaniya Rekvizitlari"), KeyboardButton(text="ℹ️ Yordam")],
        [KeyboardButton(text="❌ Bekor qilish")]
    ],
    resize_keyboard=True
)

YORDAM_TEXT = (
    "<b>Botdan foydalanish:</b>\n\n"
    "📝 <b>Xodim Shartnomasi</b> — xodim bilan mehnat shartnomasi (4 bosqich).\n"
    "🤝 <b>Hamkor Shartnomasi</b> — hamkor bilan hamkorlik shartnomasi (4 bosqich).\n"
    "🏢 <b>Kompaniya Rekvizitlari</b> — BM Akademiyasi rekvizitlari.\n"
    "❌ <b>Bekor qilish</b> yoki /cancel — joriy jarayonni to'xtatish.\n\n"
    "Har bir bosqichda javobni yozib yoki ovozli xabar (golos) qilib yuborishingiz mumkin. "
    "Oxirida shartnoma PDF ko'rinishida yuboriladi."
)


@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Assalomu alaykum! <b>BM Akademiyasi</b> shartnoma yaratish botiga xush kelibsiz.\n\n"
        "Tugmalardan birini tanlang. Ovozli xabar (golos) yuborishingiz ham mumkin!",
        reply_markup=main_kb
    )


@dp.message(Command("help"))
@dp.message(F.text == "ℹ️ Yordam")
async def help_cmd(message: types.Message):
    await message.answer(YORDAM_TEXT, reply_markup=main_kb)


@dp.message(Command("cancel"))
@dp.message(F.text == "❌ Bekor qilish")
async def cancel_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Jarayon bekor qilindi. Kerakli bo'limni tanlang.", reply_markup=main_kb)


@dp.message(F.text == "🏢 Kompaniya Rekvizitlari")
async def rekvizit_cmd(message: types.Message):
    if REKVIZITLAR:
        text = f"<b>BM Akademiyasi rekvizitlari:</b>\n\n{escape(REKVIZITLAR)}"
    else:
        text = "Rekvizitlar hali kiritilmagan. Administrator REKVIZITLAR o'zgaruvchisini sozlashi kerak."
    await message.answer(text, reply_markup=main_kb)


async def get_text_from_message(message: types.Message) -> str | None:
    """Matn yoki ovozli xabardan matn oladi. Boshqa turdagi xabarlar uchun None."""
    if message.voice:
        if not client:
            await message.answer("Ovozli xabarni matnga aylantirish o'chirilgan (OpenAI kaliti kiritilmagan). Iltimos, yozib yuboring.")
            return None
        buf = BytesIO()
        await bot.download(message.voice, destination=buf)
        try:
            transcript = await client.audio.transcriptions.create(
                model="whisper-1",
                file=("voice.ogg", buf.getvalue()),
                language="uz"
            )
        except Exception:
            logging.exception("Ovozni matnga aylantirishda xato")
            await message.answer("Ovozli xabarni tushunib bo'lmadi. Iltimos, qaytadan yuboring yoki yozing.")
            return None
        text = transcript.text.strip()
        await message.answer(f"🎙 Qabul qilindi: <i>{escape(text)}</i>")
        return text
    if message.text:
        return message.text.strip()
    await message.answer("Iltimos, javobni matn yoki ovozli xabar ko'rinishida yuboring.")
    return None


def build_pdf(path: str, title: str, intro: str, items: list[tuple[str, str]]):
    title_style = ParagraphStyle("title", fontName="DejaVu-Bold", fontSize=16, leading=20, alignment=TA_CENTER)
    body_style = ParagraphStyle("body", fontName="DejaVu", fontSize=11, leading=15)
    label_style = ParagraphStyle("label", parent=body_style, fontName="DejaVu-Bold", spaceBefore=8)

    story = [
        Paragraph(escape(title), title_style),
        Spacer(1, 8),
        Paragraph(f"Sana: {date.today().strftime('%d.%m.%Y')}", body_style),
        Spacer(1, 12),
        Paragraph(escape(intro), body_style),
    ]
    for i, (label, value) in enumerate(items, 1):
        story.append(Paragraph(f"{i}. {escape(label)}:", label_style))
        story.append(Paragraph(escape(value or "-").replace("\n", "<br/>"), body_style))
    story += [
        Spacer(1, 30),
        Paragraph(f"Direktor: {escape(DIREKTOR)} ____________", body_style),
        Spacer(1, 16),
        Paragraph("Ikkinchi tomon: ____________", body_style),
    ]
    SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50).build(story)


async def send_pdf(message: types.Message, filename: str, title: str, intro: str, items: list[tuple[str, str]]):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, filename)
        build_pdf(path, title, intro, items)
        await message.answer_document(FSInputFile(path), caption="✅ Shartnoma tayyor bo'ldi!", reply_markup=main_kb)


# ---------- Xodim shartnomasi ----------

@dp.message(F.text == "📝 Xodim Shartnomasi")
async def start_xodim(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(XodimForm.xodim_info)
    await message.answer("<b>1-bosqich:</b> Xodimning F.I.Sh., pasport seriyasi, manzili va tel raqamini ayting yoki yozing:")


@dp.message(XodimForm.xodim_info)
async def process_xodim(message: types.Message, state: FSMContext):
    txt = await get_text_from_message(message)
    if txt is None:
        return
    await state.update_data(xodim=txt)
    await state.set_state(XodimForm.loyixa_info)
    await message.answer("<b>2-bosqich:</b> Loyiha nomi va lavozimni ayting yoki yozing:")


@dp.message(XodimForm.loyixa_info)
async def process_loyixa(message: types.Message, state: FSMContext):
    txt = await get_text_from_message(message)
    if txt is None:
        return
    await state.update_data(loyixa=txt)
    await state.set_state(XodimForm.oylik_info)
    await message.answer("<b>3-bosqich:</b> Oylik ish haqi va to'lov muddatlarini ayting yoki yozing:")


@dp.message(XodimForm.oylik_info)
async def process_oylik(message: types.Message, state: FSMContext):
    txt = await get_text_from_message(message)
    if txt is None:
        return
    await state.update_data(oylik=txt)
    await state.set_state(XodimForm.kpi_info)
    await message.answer("<b>4-bosqich:</b> Sotuv rejasi va KPI bonuslarini ayting yoki yozing:")


@dp.message(XodimForm.kpi_info)
async def process_kpi(message: types.Message, state: FSMContext):
    txt = await get_text_from_message(message)
    if txt is None:
        return
    data = await state.get_data()
    await state.clear()
    await send_pdf(
        message,
        f"Xodim_shartnomasi_{message.from_user.id}.pdf",
        "IKKI TOMONLAMA MEHNAT SHARTNOMASI",
        "BM Akademiyasi va Xodim o'rtasidagi kelishuv:",
        [
            ("Xodim ma'lumotlari", data.get("xodim")),
            ("Lavozim va Loyiha", data.get("loyixa")),
            ("Mehnatga haq to'lash", data.get("oylik")),
            ("KPI va Bonuslar", txt),
        ],
    )


# ---------- Hamkor shartnomasi ----------

@dp.message(F.text == "🤝 Hamkor Shartnomasi")
async def start_hamkor(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(HamkorForm.hamkor_info)
    await message.answer("<b>1-bosqich:</b> Hamkor kompaniya nomi, rahbari, STIR va manzilini ayting yoki yozing:")


@dp.message(HamkorForm.hamkor_info)
async def process_hamkor(message: types.Message, state: FSMContext):
    txt = await get_text_from_message(message)
    if txt is None:
        return
    await state.update_data(hamkor=txt)
    await state.set_state(HamkorForm.predmet_info)
    await message.answer("<b>2-bosqich:</b> Hamkorlik predmeti (nima ish qilinadi) va tomonlar majburiyatlarini ayting yoki yozing:")


@dp.message(HamkorForm.predmet_info)
async def process_predmet(message: types.Message, state: FSMContext):
    txt = await get_text_from_message(message)
    if txt is None:
        return
    await state.update_data(predmet=txt)
    await state.set_state(HamkorForm.tolov_info)
    await message.answer("<b>3-bosqich:</b> To'lov shartlari va daromad taqsimotini ayting yoki yozing:")


@dp.message(HamkorForm.tolov_info)
async def process_tolov(message: types.Message, state: FSMContext):
    txt = await get_text_from_message(message)
    if txt is None:
        return
    await state.update_data(tolov=txt)
    await state.set_state(HamkorForm.muddat_info)
    await message.answer("<b>4-bosqich:</b> Shartnoma muddati va qo'shimcha shartlarni ayting yoki yozing:")


@dp.message(HamkorForm.muddat_info)
async def process_muddat(message: types.Message, state: FSMContext):
    txt = await get_text_from_message(message)
    if txt is None:
        return
    data = await state.get_data()
    await state.clear()
    await send_pdf(
        message,
        f"Hamkor_shartnomasi_{message.from_user.id}.pdf",
        "HAMKORLIK SHARTNOMASI",
        "BM Akademiyasi va Hamkor o'rtasidagi kelishuv:",
        [
            ("Hamkor ma'lumotlari", data.get("hamkor")),
            ("Hamkorlik predmeti va majburiyatlar", data.get("predmet")),
            ("To'lov shartlari", data.get("tolov")),
            ("Muddat va qo'shimcha shartlar", txt),
        ],
    )


@dp.message(StateFilter(None))
async def fallback(message: types.Message):
    await message.answer("Iltimos, quyidagi tugmalardan birini tanlang.", reply_markup=main_kb)


async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
