# 🤖 AI Hodimlar platformasi

Biznesmenlarga **AI hodimlar** va ularning **virtual ofisini** sotish uchun platforma.
Har bir hodim — bazaviy shablon (miya + instruksiya + ko'nikmalar). Mijozga sotilganda shablondan
**alohida nusxa** olinadi, shuning uchun bitta hodimni cheksiz mijozga sotish mumkin.

## Imkoniyatlar

- **40 ta hodim shabloni**, 11 ta bo'lim (ro'yxat pastda) — har biriga o'zbek tilida instruksiya yozilgan.
- **Nusxalash**: shablon o'zgarmaydi; har mijozdagi hodimga alohida ism va qo'shimcha ko'rsatma beriladi.
- **AI HR-direktor**: mijozning biznes tavsifini o'qib, kerakli hodimlarni o'zi tanlaydi va sozlaydi ("🤖 AI jamoani o'zi tuzsin").
- **24/7 bilim yangilash**: har rol o'z sohasidagi yangiliklarni (Google News, kun.uz) har 6 soatda o'qib,
  o'zbekcha xulosa qilib bilim bazasiga yozadi. Bilim shablonga yoziladi — barcha sotilgan nusxalar birdaniga aqlliroq bo'ladi.
  Suhbat paytida hodim kerak bo'lsa internetdan qidiradi (web search).
- **Vazifa berish**: hodimga vazifa bersangiz, u fonda bajaradi; ofisda stolida "ishlayapti" holatida ko'rinadi.
- **Jonli virtual ofis**: hodimlar stollarda ishlaydi, kofega, davra stoliga, majlis xonasiga, sport zalga yuradi.
  4 hajm (kichik 6 / o'rta 12 / katta 24 / mega 48 o'rin) va 4 dizayn (klassik, tungi, yashil, premium).
- **O'zbekcha ovoz (golos)**: 🎤 tugmasi — brauzer uz-UZ tanish; bo'lmasa Whisper (uzbek). Javobni ovozda o'qish.
- **Admin panel** to'liq o'zbek tilida: mijozlar, ofislar, katalog, komplektlar, bilim bazasi.

## Hodimlar qayerda ishlaydi: Telegram guruh + AI Direktor

```
Biznesmen (Telegram guruhda yozadi yoki 🎤 gapiradi)
        │
        ▼
👔 AI Direktor ── reja tuzadi: kim, nima, qaysi bosqichda
        │
        ├─ 1-bosqich (parallel):  📱 SMM   🎯 Target   🔭 Tadqiqotchi
        ├─ 2-bosqich (1-bosqich natijalarini ko'radi):  ✍️ Kopirayter
        ▼
👔 Direktor natijalarni tekshirib, guruhga yakuniy hisobot yozadi
```

- Har ofisda avtomatik bitta **AI Direktor** bo'ladi (virtual ofisda rahbar kabinetida o'tiradi).
- Har bir hodimning javobi guruhga uning ismi va lavozimi bilan yoziladi; ofis ko'rinishida esa ular stolida "ishlayapti" bo'lib turadi.
- `Aziz, ...` deb yozilsa — direktorsiz, to'g'ridan-to'g'ri shu hodim javob beradi.
- Buyruqlar: `/ulash KOD`, `/jamoa`, `/hisobot`.
- Admin paneldan ham "🎯 Direktorga topshiriq" berish mumkin; guruh ulangan bo'lsa natijalar guruhga ham boradi.

**Ulash:** BotFather'da bot yarating → `AI_HODIM_BOT_TOKEN` ni serverga qo'shing → biznesmen botni guruhga qo'shib
**admin qiladi** (yoki BotFather'da `/setprivacy` → Disable) → guruhga admin paneldagi "📲 Telegram" oynasidagi `/ulash KOD` ni yozadi.
Bitta bot hamma mijozlarga xizmat qiladi; har bir guruh o'z ofisiga ulanadi.

## Railway'ga joylash

Repoda tayyor: `ai_hodimlar/Dockerfile` va `ai_hodimlar/railway.json` (healthcheck `/salomatlik`, 1 nusxa).

1. railway.app → **New Project → Deploy from GitHub repo** → `Shartnomaa-bot`.
2. Servis **Settings**:
   - *Source → Branch*: `claude/ai-hodimlar-platform-xx0ioe` (yoki main'ga merge qilgach `main`);
   - *Config-as-code → Railway Config File*: `ai_hodimlar/railway.json`.
3. **Variables**: `ANTHROPIC_API_KEY`, `ADMIN_TOKEN`, `AI_HODIM_BOT_TOKEN`, (ixtiyoriy) `OPENAI_API_KEY`.
4. Servisga o'ng tugma → **Attach Volume** → mount path: `/data` (bazа shu yerda saqlanadi, deploy'da o'chmaydi).
5. **Settings → Networking → Generate Domain** → linkni oching, `ADMIN_TOKEN` parolini kiriting.

Shartnoma boti (`main.py`) alohida servis bo'lib qoladi; bu panel unga tegmaydi.

## Ishga tushirish

```bash
pip install -r ai_hodimlar/requirements.txt
export ANTHROPIC_API_KEY=...     # hodimlar miyasi (Claude). Kalitsiz demo rejimda ishlaydi
export OPENAI_API_KEY=...        # ixtiyoriy: o'zbekcha ovozni tanish/o'qish (Whisper, TTS)
export ADMIN_TOKEN=maxfiy-parol  # admin panel paroli (tavsiya etiladi)
export AI_HODIM_BOT_TOKEN=...    # Telegram bot (BotFather). Shartnoma botingizdan alohida bot bo'lsin
uvicorn ai_hodimlar.server:app --host 0.0.0.0 --port 8000   # faqat 1 worker (Telegram polling uchun)
```

Brauzerda `http://localhost:8000` ni oching.

| O'zgaruvchi | Standart | Tavsif |
|---|---|---|
| `AI_HODIM_MODEL` | `claude-opus-5-5` | Hodimlar suhbati va vazifalari uchun model |
| `AI_BILIM_MODEL` | `claude-haiku-5-5` | Yangiliklarni xulosalash (arzon model) |
| `BILIM_INTERVAL_SOAT` | `6` | Bilim yangilash oralig'i |
| `BILIM_YANGILASH` | `1` | `0` — fon yangilashni o'chirish |
| `VAZIFA_ISHCHILAR` | `4` | Bir vaqtda bajariladigan vazifalar soni |
| `TELEGRAM_ISHCHILAR` | `8` | Bir vaqtda ishlanadigan Telegram xabarlari |
| `AI_HODIMLAR_DB` | `ai_hodimlar/ai_hodimlar.db` | SQLite fayli |

Claude so'rovlarida server tomonidagi zaxira model (`fallbacks: "default"`) yoqilgan: model so'rovni rad etsa, API uni avtomatik boshqa modelda qayta bajaradi.

## Tuzilma

| Fayl | Vazifa |
|---|---|
| `catalog.py` | Hodimlar shablonlari, instruksiyalar, komplektlar, ofis hajmlari |
| `brain.py` | Claude bilan suhbat, vazifa bajarish, AI HR-direktor, bilim xulosasi |
| `direktor.py` | AI Direktor: reja, vazifa taqsimlash, bosqichma-bosqich bajarish, hisobot |
| `telegram.py` | Telegram guruh boti (server ichida long-polling, alohida jarayon shart emas) |
| `knowledge.py` | 24/7 yangiliklarni o'qib bilim bazasini yangilash |
| `server.py` | FastAPI: admin API, ovoz, frontend |
| `static/office.js` | Jonli 2D ofis (canvas) |
| `static/app.js` | Admin panel |

## Instruksiyalar manbasi haqida

Instruksiyalar shu loyiha uchun noldan, O'zbekiston bozoriga moslab yozilgan. Ochiq manbali AI agentlar
to'plamlari (masalan GitHub'dagi `wshobson/agents`, `VoltAgent/awesome-claude-code-subagents`,
`anthropics/skills`) g'oya sifatida o'rganishga arziydi, lekin ulardan matn ko'chirilmagan — ularni
mahsulotga qo'shishdan oldin har birining litsenziyasini tekshiring.

## Hodimlar ro'yxati

**Sotuv**

| # | Hodim | Nima qiladi | Asosiy ko'nikmalar |
|---|---|---|---|
| 1 | 💼 Sotuv menejeri | Lidlarni saralaydi, tijoriy taklif yozadi, e'tirozlarni yopadi, sotuvni yakunlaydi. | Lid kvalifikatsiyasi (BANT/SPIN), Tijoriy taklif, E'tirozlar bilan ishlash, Sotuv skriptlari |
| 2 | 💬 Telegram/Instagram sotuvchi | Direkt va Telegramdagi yozishmalarga 24/7 javob beradi, buyurtma oladi. | Tezkor javob, Mahsulot katalogi bo'yicha maslahat, Buyurtma rasmiylashtirish, Upsell/cross-sell |
| 3 | 📞 Call-markaz operatori | Ovozli qo'ng'iroqlar skripti, kiruvchi/chiquvchi qo'ng'iroqlar, eslatmalar. | Qo'ng'iroq skripti, Ovozli muloqot, Uchrashuvga yozish, Sovuq qo'ng'iroq |
| 4 | 🗂️ CRM menejeri | Voronkani tartibda saqlaydi, yo'qolgan lidlarni topadi, hisobot beradi. | Sotuv voronkasi, AmoCRM/Bitrix24, Konversiya tahlili, Avtomatlashtirish |

**Marketing**

| # | Hodim | Nima qiladi | Asosiy ko'nikmalar |
|---|---|---|---|
| 5 | 📱 SMM menejer | Instagram, Telegram, TikTok uchun kontent-reja, postlar, stories, tahlil. | Kontent-reja, Post va stories matni, Reels g'oyalari, Trendlar monitoringi |
| 6 | ✍️ Kopirayter | Sotuvchi matnlar: reklama, landing, mahsulot tavsifi, e-mail, skript. | AIDA/PAS formulalari, Landing matni, Mahsulot tavsifi, Sarlavhalar |
| 7 | 🎯 Target reklama mutaxassisi | Meta, Google, Yandex, Telegram Ads kampaniyalarini rejalashtiradi va optimallashtiradi. | Auditoriya segmentatsiyasi, Kreativ test (A/B), Byudjet taqsimoti, CPL/CPA/ROAS tahlili |
| 8 | 🔎 SEO mutaxassisi | Sayt va kontentni Google/Yandex qidiruvi va AI-qidiruv uchun optimallashtiradi. | Kalit so'zlar tadqiqoti, On-page SEO, Maqola strukturasi, Texnik audit |
| 9 | 🎬 Video ssenariy muallifi | Reels, TikTok, YouTube Shorts uchun ssenariylar, hook va montaj ko'rsatmalari. | Hook (birinchi 3 soniya), Ssenariy tuzilmasi, Kadr-kadr reja, Trend audio |
| 10 | 📧 E-mail/SMS marketolog | Xabarnomalar, avtomatik zanjirlar, qayta sotuv kampaniyalari. | Avtovoronka, Segmentatsiya, SMS/push matnlari, Qayta faollashtirish |
| 11 | 🧭 Brend strateg | Pozitsiyalash, brend ovozi, raqobatchilardan farqlanish strategiyasi. | Pozitsiyalash, Brend ovozi, Raqobat tahlili, Mijoz portreti (ICP) |

**Mijozlarga xizmat**

| # | Hodim | Nima qiladi | Asosiy ko'nikmalar |
|---|---|---|---|
| 12 | 🎧 Qo'llab-quvvatlash operatori 24/7 | Mijozlar savollariga kecha-kunduz javob beradi, muammolarni hal qiladi. | FAQ bo'yicha javob, Muammoni aniqlash, Eskalatsiya, Empatik muloqot |
| 13 | 🤝 Mijozlarni ushlab qolish menejeri | Shikoyatlar, qaytarishlar, ketayotgan mijozlarni qaytarish, NPS so'rovnomalar. | Shikoyatlar bilan ishlash, NPS/CSAT, Sodiqlik dasturi, Churn tahlili |

**Moliya**

| # | Hodim | Nima qiladi | Asosiy ko'nikmalar |
|---|---|---|---|
| 14 | 🧮 Buxgalter | O'zbekiston soliq qonunchiligi bo'yicha hisob, hisobotlar, soliq kalendari. | Soliq kodeksi (O'zR), QQS, foyda, aylanma solig'i, Hisob-faktura (Didox, Faktura.uz), Ish haqi va INPS |
| 15 | 📊 Moliyaviy tahlilchi (CFO yordamchisi) | P&L, pul oqimi, unit-ekonomika, byudjet va prognozlar. | P&L va Cash-flow, Unit-ekonomika, Byudjetlash, Moliyaviy model |
| 16 | 💳 Debitorlik qarzi nazoratchisi | To'lov muddatlarini kuzatadi, eslatma yuboradi, qarzlarni undiradi. | To'lov eslatmalari, Qarz reestri, Muzokara, To'lov jadvali |

**HR**

| # | Hodim | Nima qiladi | Asosiy ko'nikmalar |
|---|---|---|---|
| 17 | 🧑‍💼 HR rekruter | Vakansiya matni, rezyume saralash, intervyu savollari, nomzodlarni baholash. | Vakansiya yozish, Rezyume skrining, Intervyu savollari, Kompetensiya modeli |
| 18 | 🌱 HR menejer | Onboarding, KPI, motivatsiya, ichki qoidalar, mehnat shartnomalari. | Onboarding rejasi, KPI tizimi, Mehnat kodeksi (O'zR), Korporativ madaniyat |
| 19 | 🎓 Korporativ trener | Xodimlar uchun treninglar, testlar, sotuv va xizmat standartlari. | Trening dasturi, Test va attestatsiya, Rol o'yinlari, Standartlar kitobi |

**Yuridik**

| # | Hodim | Nima qiladi | Asosiy ko'nikmalar |
|---|---|---|---|
| 20 | ⚖️ Yurist | Shartnomalar tuzish va tekshirish, huquqiy maslahat, pretenziyalar. | Shartnoma tuzish, Xavflarni aniqlash, Fuqarolik kodeksi (O'zR), Pretenziya va da'vo |
| 21 | 🛡️ Muvofiqlik (compliance) mutaxassisi | Shaxsiy ma'lumotlar, iste'molchi huquqlari, tekshiruvlarga tayyorgarlik. | Shaxsiy ma'lumotlar qonuni, Iste'molchilar huquqlari, Ichki nazorat, Tekshiruvga tayyorgarlik |

**Operatsiya**

| # | Hodim | Nima qiladi | Asosiy ko'nikmalar |
|---|---|---|---|
| 22 | 📋 Loyiha menejeri | Vazifalarni taqsimlaydi, muddatlarni nazorat qiladi, AI jamoani boshqaradi. | Vazifa dekompozitsiyasi, Gantt/Kanban, Risk boshqaruvi, Kundalik stendap |
| 23 | 📈 Biznes-analitik | Ma'lumotlarni tahlil qiladi, dashboard va KPI, jarayonlarni optimallashtiradi. | Excel/Google Sheets, SQL, KPI dashboard, Jarayon xaritasi |
| 24 | 🚚 Ombor va logistika menejeri | Zaxiralar, yetkazib berish, ombor hisob-kitobi, kuryerlar marshruti. | Zaxira nazorati (ABC/XYZ), Yetkazish rejasi, Kuryer marshruti, Inventarizatsiya |
| 25 | 🛒 Xaridlar menejeri | Yetkazib beruvchilarni topadi, narxlarni solishtiradi, xaridlarni rejalashtiradi. | Yetkazib beruvchi qidirish, Narx taqqoslash, Muzokara, Import (Xitoy, Turkiya) |

**IT**

| # | Hodim | Nima qiladi | Asosiy ko'nikmalar |
|---|---|---|---|
| 26 | 👨‍💻 Full-stack dasturchi | Sayt, bot, CRM integratsiyalar, avtomatlashtirish skriptlari yozadi. | Python/JS/TS, Telegram botlar, API integratsiya, Ma'lumotlar bazasi |
| 27 | 🧪 QA tester | Test-keyslar, xatolarni topish, sifat nazorati. | Test-keys yozish, Regressiya testi, Bug-report, Avtotest |
| 28 | ⚙️ DevOps muhandisi | Serverlar, deploy, monitoring, zaxira nusxa. | Docker, CI/CD, Linux server, Monitoring |
| 29 | 🔐 Kiberxavfsizlik mutaxassisi | Xavfsizlik auditi, parollar siyosati, firibgarlik va fishingdan himoya. | Xavfsizlik auditi, Fishing tahlili, Parol siyosati, Zaxira va tiklash |
| 30 | 🎨 UI/UX va grafik dizayner | Sayt, ilova, banner va kreativlar uchun dizayn g'oyalari, ТЗ, AI-rasm promptlari. | UI/UX, Banner va kreativ, Brendbuk, AI-rasm promptlari |

**Boshqaruv**

| # | Hodim | Nima qiladi | Asosiy ko'nikmalar |
|---|---|---|---|
| 31 | 🗓️ Rahbar yordamchisi (kotib) | Kun tartibi, uchrashuvlar, xatlar, protokollar, eslatmalar. | Kalendar boshqaruvi, Xat yozish, Uchrashuv protokoli, Vazifa nazorati |
| 32 | ♟️ Strategik maslahatchi | Biznes-model, o'sish strategiyasi, yangi yo'nalishlar, investitsiya qarorlari. | Biznes-model, SWOT/PESTEL, O'sish strategiyasi, Franshiza |
| 33 | 🔭 Bozor va raqobatchilar tadqiqotchisi | Bozorni 24/7 kuzatadi: raqobatchilar narxi, yangiliklar, trendlar, imkoniyatlar. | Raqobatchilar monitoringi, Narxlar tahlili, Trendlar, Bozor hajmi (TAM/SAM/SOM) |

**Sohaviy**

| # | Hodim | Nima qiladi | Asosiy ko'nikmalar |
|---|---|---|---|
| 34 | 🛍️ Marketplace menejeri (Uzum, Wildberries, Ozon) | Kartochkalar, narx, reklama, sharhlar, zaxira - marketplace savdosini o'stiradi. | Kartochka SEO, Narx strategiyasi, Ichki reklama, Sharhlarga javob |
| 35 | 🏠 Ko'chmas mulk agenti | Obyekt e'lonlari, mijoz bilan muloqot, ko'rishga yozish, narx tahlili. | E'lon matni, Narx bahosi, Ko'rishga yozish, Ipoteka hisobi |
| 36 | 📚 O'quv markazi metodisti | Kurs dasturlari, darslar, testlar, o'quvchilar bilan muloqot. | O'quv dasturi, Dars rejasi, Test tuzish, O'quvchi progressi |
| 37 | 🏥 Klinika administratori | Qabulga yozish, eslatmalar, narxlar, bemorlar savollariga javob. | Qabulga yozish, Shifokorlar jadvali, Eslatma SMS, Xizmatlar narxi |
| 38 | 🍽️ Restoran/kafe menejeri | Bron, menyu, yetkazib berish buyurtmalari, food-cost, sharhlar. | Stol bron qilish, Menyu muhandisligi, Food-cost, Yetkazib berish (Wolt, Yandex Eda, Express24) |
| 39 | ✈️ Turizm menejeri | Turlar, viza, mehmonxona, aviabilet, mijozga marshrut. | Tur paketlar, Viza talablari, Marshrut tuzish, Narx kalkulyatsiyasi |
| 40 | 🌐 Tarjimon (uz/ru/en/tr) | Hujjatlar, yozishmalar, sayt va marketing matnlarini tarjima qiladi. | O'zbek (lotin/kirill), Rus, Ingliz, Turk |

| Komplekt | Hodimlar | Ofis | Narx (tavsiya) |
|---|---|---|---|
| Start ofis | 5 | kichik | $299/oy |
| Biznes ofis | 10 | orta | $549/oy |
| Korporativ ofis | 20 | katta | $999/oy |
| Marketplace sotuvchi | 5 | kichik | $349/oy |
| Restoran | 5 | kichik | $299/oy |
| Klinika | 5 | kichik | $349/oy |
| O'quv markazi | 8 | orta | $449/oy |
| IT kompaniya | 9 | orta | $649/oy |
