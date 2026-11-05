"""
UZEX AI Hackathon - Saralash bosqichi
Birja bitimlari bo'yicha savollarga FAQAT ma'lumotlar asosida javob beruvchi veb-servis.

Ishga tushirish:
    pip install -r requirements.txt
    python app.py
Brauzerda: http://127.0.0.1:5000
"""

from __future__ import annotations

import glob
import math
import os
import re

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, static_folder=STATIC_DIR)

# --- Gemini (ixtiyoriy) ---------------------------------------------------
# Kalit hech qachon kodga yozilmaydi. U faqat muhit o'zgaruvchisidan o'qiladi:
#   Linux/Mac:  export GEMINI_API_KEY="..."
#   Windows:    set GEMINI_API_KEY=...
# Kalit bo'lmasa yoki google-genai o'rnatilmagan bo'lsa, servis baribir
# ma'lumot asosidagi qidiruv bilan ishlayveradi (LLM shart emas).
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
_gemini_client = None

if GEMINI_API_KEY:
    try:
        from google import genai
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        print("[ok] Gemini ulandi.")
    except Exception as exc:  # noqa: BLE001
        print(f"[ogohlantirish] Gemini ulanmadi, faqat qidiruv ishlaydi: {exc}")
        _gemini_client = None
else:
    print("[info] GEMINI_API_KEY topilmadi. Faqat qidiruv asosida javob beriladi.")

NO_ANSWER = {
    "uz": "Ma'lumotda javob yo'q.",
    "ru": "В данных ответа нет.",
}

# Qidiruvda e'tiborga olinmaydigan so'zlar (o'zbek va rus)
STOPWORDS = {
    "va", "bu", "bilan", "uchun", "qanday", "nima", "qaysi", "necha", "kim",
    "haqida", "ham", "yoki", "bo'yicha", "bo'lgan", "bo'ladi", "ni", "ning",
    "da", "dan", "ga", "ga", "is", "the", "of", "и", "в", "на", "что", "как",
    "какой", "какая", "какие", "это", "по", "для", "с", "со", "о", "об",
}

WORD_RE = re.compile(r"[\w'’`-]+", re.UNICODE)
CYRILLIC_RE = re.compile(r"[а-яА-ЯёЁ]")

# Ma'lumotlar yuklanganda bir marta hisoblanadi
DF = pd.DataFrame()
SEARCH_TEXT = pd.Series(dtype=str)


def detect_language(text: str) -> str:
    """Savol kirill yozuvida bo'lsa rus, aks holda o'zbek tilida javob beramiz."""
    return "ru" if CYRILLIC_RE.search(text or "") else "uz"


def normalize(text: str) -> str:
    text = str(text).lower()
    return text.replace("’", "'").replace("‘", "'").replace("`", "'")


def tokenize(text: str):
    tokens = []
    for tok in WORD_RE.findall(normalize(text)):
        tok = tok.strip("-'")
        if len(tok) > 1 and tok not in STOPWORDS:
            tokens.append(tok)
    # takrorlanuvchi so'zlarni olib tashlaymiz, tartibni saqlaymiz
    return list(dict.fromkeys(tokens))


def load_data() -> None:
    """data/ papkasidagi CSV, XLSX yoki JSON fayllarini yuklaydi."""
    global DF, SEARCH_TEXT
    os.makedirs(DATA_DIR, exist_ok=True)
    frames = []

    for path in sorted(glob.glob(os.path.join(DATA_DIR, "*"))):
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".csv":
                df = pd.read_csv(path, dtype=str, keep_default_na=False)
            elif ext in (".xlsx", ".xls"):
                df = pd.read_excel(path, dtype=str).fillna("")
            elif ext == ".json":
                df = pd.read_json(path, dtype=False)
            else:
                continue
        except Exception as exc:  # noqa: BLE001
            print(f"[ogohlantirish] {path} o'qilmadi: {exc}")
            continue
        frames.append(df.astype(str))

    if not frames:
        DF = pd.DataFrame()
        SEARCH_TEXT = pd.Series(dtype=str)
        print("[ogohlantirish] data/ papkasida ma'lumot topilmadi.")
        return

    DF = pd.concat(frames, ignore_index=True).fillna("")
    DF.columns = [str(c).strip() for c in DF.columns]
    # Qidiruv uchun barcha ustunlarni bitta matnga yig'amiz (kichik harf)
    SEARCH_TEXT = DF.apply(lambda row: " | ".join(row.values), axis=1).str.lower()
    print(f"[ok] {len(DF)} ta yozuv yuklandi.")


def search(question: str, top_k: int = 5):
    """Savol so'zlariga mos keladigan yozuvlarni topadi (ball bo'yicha tartiblangan)."""
    if DF.empty:
        return []

    tokens = tokenize(question)
    if not tokens:
        return []

    scores = pd.Series(0, index=SEARCH_TEXT.index, dtype="int32")
    for tok in tokens:
        scores += SEARCH_TEXT.str.contains(re.escape(tok), regex=True).astype("int32")

    # Kamida yarim so'z mos kelishi shart (kamida 1 ta)
    min_score = 1 if len(tokens) == 1 else max(2, math.ceil(len(tokens) * 0.5))
    mask = scores >= min_score
    if not mask.any():
        return []

    matched = scores[mask].sort_values(ascending=False).head(top_k)
    results = []
    for idx, score in matched.items():
        record = DF.loc[idx].to_dict()
        results.append({"score": int(score), "record": record})
    return results


def format_answer(results, lang: str) -> str:
    """Faqat topilgan ma'lumotdan javob tuzadi, hech narsa qo'shmaydi."""
    if not results:
        return NO_ANSWER[lang]

    if lang == "ru":
        head = f"Найдено записей: {len(results)}."
    else:
        head = f"Topilgan yozuvlar soni: {len(results)}."

    lines = [head]
    for i, item in enumerate(results, start=1):
        fields = "; ".join(f"{k}: {v}" for k, v in item["record"].items() if str(v).strip())
        lines.append(f"{i}) {fields}")
    return "\n".join(lines)


def llm_rephrase(question: str, results: list, lang: str) -> str | None:
    """Topilgan yozuvlarni Gemini yordamida tabiiy tilda tushuntiradi.
    LLM'ga FAQAT topilgan yozuvlar beriladi — tashqi bilim yoki taxmin
    qo'shilmasligi aniq ko'rsatma bilan taqiqlanadi. Xatolik bo'lsa None
    qaytaradi va chaqiruvchi tomon oddiy formatga qaytadi (fallback)."""
    if _gemini_client is None or not results:
        return None

    lang_name = "ruscha" if lang == "ru" else "o'zbekcha"
    records_text = "\n".join(
        "; ".join(f"{k}: {v}" for k, v in item["record"].items() if str(v).strip())
        for item in results
    )
    prompt = (
        "Sen birja bitimlari bo'yicha ma'lumotga asoslangan yordamchisan. "
        "Qoidalar: FAQAT quyida berilgan yozuvlardan foydalan; ularda yo'q "
        "hech qanday faktni, raqamni yoki izohni qo'shma; taxmin qilma; "
        f"javobni {lang_name} tilda, qisqa va aniq yoz; raqam, nom va kod "
        "kabi muhim qiymatlarni albatta ko'rsat.\n\n"
        f"Yozuvlar:\n{records_text}\n\nSavol: {question}\n\nJavob:"
    )
    try:
        response = _gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        text = (response.text or "").strip()
        return text or None
    except Exception as exc:  # noqa: BLE001
        print(f"[ogohlantirish] Gemini chaqiruvi muvaffaqiyatsiz: {exc}")
        return None


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "records": int(len(DF)),
        "llm_enabled": _gemini_client is not None,
    })


@app.route("/api/ask", methods=["POST"])
def ask():
    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question", "")).strip()

    if not question:
        return jsonify({"error": "Savol bo'sh."}), 400
    if len(question) > 1000:
        return jsonify({"error": "Savol juda uzun (1000 belgidan oshmasin)."}), 400

    lang = detect_language(question)
    results = search(question)

    if not results:
        answer = NO_ANSWER[lang]
        source = "none"
    else:
        llm_text = llm_rephrase(question, results, lang)
        if llm_text:
            answer = llm_text
            source = "llm"
        else:
            answer = format_answer(results, lang)
            source = "search"

    return jsonify({
        "question": question,
        "language": lang,
        "answer": answer,
        "found": bool(results),
        "source": source,
        "matches": [r["record"] for r in results],
    })


load_data()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
