import os
import asyncio
import logging
import requests
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from openai import OpenAI

# Environment o'zgaruvchilaridan tokenlarni olish
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

class Form(StatesGroup):
    xodim_info = State()
    loyixa_info = State()
    oylik_info = State()
    kpi_info = State()

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Xodim Shartnomasi"), KeyboardButton(text="🤝 Hamkor Shartnomasi")],
        [KeyboardButton(text="🏢 Kompaniya Rekvizitlari"), KeyboardButton(text="ℹ️ Yordam")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "Assalomu alaykum! **BM Akademiyasi** shartnoma yaratish botiga xush kelibsiz.\n\n"
        "Tugmalardan birini tanlang. Ovozli xabar (golos) yuborishingiz ham mumkin!",
        reply_markup=main_kb
    )

async def get_text_from_message(message: types.Message) -> str:
    if message.voice:
        file_info = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        res = requests.get(file_url)
        ogg_file = f"voice_{message.voice.file_id}.ogg"
        with open(ogg_file, "wb") as f:
            f.write(res.content)
        
        if client:
            with open(ogg_file, "rb") as audio:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio,
                    language="uz"
                )
            os.remove(ogg_file)
            return transcript.text
        else:
            os.remove(ogg_file)
            return "Ovozli xabar qabul qilindi (OpenAI kaliti kiritilmagan)."
    return message.text or ""

@dp.message(F.text == "📝 Xodim Shartnomasi")
async def start_form(message: types.Message, state: FSMContext):
    await state.set_state(Form.xodim_info)
    await message.answer("<b>1-bosqich:</b> Xodimning F.I.Sh., pasport seriyasi, manzili va tel raqamini ayting yoki yozing:", parse_mode="HTML")

@dp.message(Form.xodim_info)
async def process_xodim(message: types.Message, state: FSMContext):
    txt = await get_text_from_message(message)
    await state.update_data(xodim=txt)
    await state.set_state(Form.loyixa_info)
    await message.answer("<b>2-bosqich:</b> Loyiha nomi va lavozimni ayting yoki yozing:", parse_mode="HTML")

@dp.message(Form.loyixa_info)
async def process_loyixa(message: types.Message, state: FSMContext):
    txt = await get_text_from_message(message)
    await state.update_data(loyixa=txt)
    await state.set_state(Form.oylik_info)
    await message.answer("<b>3-bosqich:</b> Oylik ish haqi va to'lov muddatlarini ayting yoki yozing:", parse_mode="HTML")

@dp.message(Form.oylik_info)
async def process_oylik(message: types.Message, state: FSMContext):
    txt = await get_text_from_message(message)
    await state.update_data(oylik=txt)
    await state.set_state(Form.kpi_info)
    await message.answer("<b>4-bosqich:</b> Sotuv rejasi va KPI bonuslarini ayting yoki yozing:", parse_mode="HTML")

@dp.message(Form.kpi_info)
async def process_kpi(message: types.Message, state: FSMContext):
    txt = await get_text_from_message(message)
    data = await state.get_data()
    
    pdf_filename = f"Shartnoma_{message.from_user.id}.pdf"
    c = canvas.Canvas(pdf_filename, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(180, 750, "IKKI TOMONLAMA SHARTNOMA")
    c.setFont("Helvetica", 11)
    
    textobject = c.beginText(50, 700)
    textobject.textLine("BM Akademiyasi va Xodim o'rtasidagi kelishuv:")
    textobject.textLine("")
    textobject.textLine(f"1. Xodim ma'lumotlari: {data.get('xodim')}")
    textobject.textLine(f"2. Lavozim va Loyiha: {data.get('loyixa')}")
    textobject.textLine(f"3. Mehnatga haq to'lash: {data.get('oylik')}")
    textobject.textLine(f"4. KPI va Bonuslar: {txt}")
    textobject.textLine("")
    textobject.textLine("Direktor: Bobur Mirzo Yo'ldoshboyev")
    c.drawText(textobject)
    c.save()
    
    await message.answer_document(FSInputFile(pdf_filename), caption="✅ Shartnoma tayyor bo'ldi!")
    if os.path.exists(pdf_filename):
        os.remove(pdf_filename)
    await state.clear()

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

