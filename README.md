# Birja bitimlari AI-agenti (Saralash bosqichi)

Veb-servis birja bitimlari haqidagi savollarga **faqat ma'lumotlar asosida** javob beradi.
Ma'lumot topilmasa, "Ma'lumotda javob yo'q" deb aytadi va taxmin qilmaydi.
Savol tilida javob beradi (rus yoki o'zbek).

## Tuzilishi

```
birja_agent/
├── app.py              # backend (Flask): yuklash, qidiruv, javob
├── static/index.html   # savol-javob interfeysi
├── data/               # UZEX dan yuklab olingan ma'lumotlar (CSV/XLSX/JSON)
├── requirements.txt
└── README.md
```

## O'rnatish va ishga tushirish

```bash
pip install -r requirements.txt
# Ma'lumot faylini data/ papkasiga qo'ying (namuna allaqachon bor)
python app.py
```

Brauzerda oching: http://127.0.0.1:5000

## Gemini (ixtiyoriy AI rejimi)

Servis Gemini'siz ham to'liq ishlaydi (qidiruv rejimi). Gemini yoqilsa,
topilgan yozuvlarni tabiiyroq tilda tushuntiradi — lekin faqat topilgan
yozuvlardan foydalanadi, hech narsa o'ylab topmaydi.

**MUHIM — kalitni hech qachon kodga yozmang va hech kimga ulashmang.**
Agar kalitingiz allaqachon biror joyda (chat, skrinshot, repo) ochiq
qolgan bo'lsa, uni Google AI Studio'da darhol bekor qiling (revoke) va
yangisini yarating.

```bash
pip install google-genai
export GEMINI_API_KEY="o'zingizning_yangi_kalitingiz"   # Windows: set GEMINI_API_KEY=...
python app.py
```

`GEMINI_API_KEY` o'rnatilmagan bo'lsa, servis avtomatik ravishda oddiy
qidiruv rejimida ishlayveradi — bu normal holat, xatolik emas.
`/api/health` javobidagi `llm_enabled` maydoni holatni ko'rsatadi.

## 24/7 ishga tushirish

Flask'ning o'zi (`python app.py`) faqat sinov uchun. Doimiy ishlashi
uchun `gunicorn` va bulutli hosting yoki VPS kerak.

### A) Tezkor variant — bepul bulutli hosting (Render misolida)

Bugungi muddat uchun eng tez yo'l. Railway, Fly.io yoki PythonAnywhere'da
ham deyarli bir xil qadamlar.

1. Shu `birja_agent` papkasini GitHub'ga joylang (yangi, bo'sh repo).
2. [render.com](https://render.com) da ro'yxatdan o'ting, **New → Web Service**,
   GitHub repo'ni ulang.
3. Sozlamalar:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
4. **Environment → Add Environment Variable**: `GEMINI_API_KEY` = yangi kalitingiz
   (kodga yozilmaydi, faqat shu yerga).
5. Deploy tugmasini bosing. Bir necha daqiqadan so'ng sizga doimiy havola
   beriladi (masalan `https://birja-agent.onrender.com`) — shu havola 24/7 ishlaydi.
6. Bepul reja ba'zan uyqu rejimiga o'tishi mumkin (birinchi so'rov sekinroq
   javob beradi). Hackathon uchun muammo emas, lekin doimiy tezlik kerak
   bo'lsa, pullik rejaga o'ting yoki B variantni tanlang.

### B) To'liq nazorat — o'z VPS'ingizda (systemd + nginx)

`deploy/` papkasida tayyor namunalar bor:
- `deploy/birja-agent.service` — systemd xizmat fayli (server qayta
  yonganda ham avtomatik ishga tushadi, qulasa ham qayta tiklanadi).
- `deploy/nginx.conf.sample` — nginx orqali 80-portga chiqarish namunasi.

Qisqacha qadamlar:
```bash
# serverda
sudo mkdir -p /opt/birja_agent
sudo cp -r birja_agent/* /opt/birja_agent/
cd /opt/birja_agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# deploy/birja-agent.service faylidagi yo'llarni va
# GEMINI_API_KEY qiymatini to'g'rilang, so'ng:
sudo cp deploy/birja-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now birja-agent
sudo systemctl status birja-agent   # ishlayotganini tekshirish

# domen/https kerak bo'lsa nginx + certbot qo'shiladi
```

Servis qulab tushsa, `Restart=always` tufayli systemd uni avtomatik
qayta ishga tushiradi — shu bois 24/7 uchun bu ishonchli yo'l.

## API

**POST /api/ask**
```json
{ "question": "Eng katta bitim qaysi?" }
```
Javob:
```json
{
  "question": "...",
  "language": "uz",
  "answer": "Topilgan yozuvlar soni: 1 ...",
  "found": true,
  "matches": [ { "RAQAM": "1003", "NOM": "...", "KOD": "..." } ]
}
```

**GET /api/health**: servis holati va yuklangan yozuvlar soni.

## Ishlash printsipi

1. Ma'lumotlar ishga tushganda bir marta yuklanadi.
2. Savol so'zlari (stop-so'zlardan tashqari) barcha ustunlardan qidiriladi.
3. Eng mos yozuvlar tanlanadi. Kamida yarim so'z mos kelishi shart.
4. Mos yozuv topilmasa, "Ma'lumotda javob yo'q" qaytariladi.
5. Javob faqat topilgan yozuv maydonlaridan tuziladi, tashqi bilim qo'shilmaydi.

## Muhim eslatma

Ma'lumot fayli ustunlari nomi har xil bo'lishi mumkin. Dastur barcha ustunlarni avtomatik qidiradi, shuning uchun ustun nomlarini qo'lda o'zgartirish shart emas. Haqiqiy ma'lumotlarni yuklab, `/api/health` orqali yozuvlar soni to'g'ri chiqqanini tekshiring.
