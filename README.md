# 💊 TharmYa AI

> **ถามก่อนซื้อยา ปลอดภัยกว่า** — ผู้ช่วย AI แนะนำยาสามัญ (OTC) สำหรับคนไทย พร้อม RAG knowledge base และ safety guardrails

CS460 Artificial Intelligence | Final Project

---

## ✨ เด่นอะไร

- **🎯 RAG (Retrieval-Augmented Generation)** — TF-IDF index บนฐานข้อมูลยา 25 ตัว → ดึงเฉพาะยาที่ตรงอาการให้ LLM พิจารณา (ลด token + ลด hallucination)
- **🛡️ Safety Guardrails** — pre-check ก่อนถึง LLM: เคสฉุกเฉิน (`เจ็บหน้าอก`, `หายใจไม่ออก`) ตัด short-circuit เรียก 1669 / คำถามนอกขอบเขต / ยาที่ต้องสั่งโดยแพทย์
- **🔄 Multi-Provider** — รองรับ Gemini, OpenAI, OpenRouter, Groq, Cerebras, Ollama (local) — สลับด้วย env vars ไม่ต้องแก้ code
- **🧓 UI สำหรับผู้สูงอายุ** — font ใหญ่, ปุ่มใหญ่, quick-pick symptoms, ฟอนต์ Sarabun, contrast สูง
- **✅ Validation Framework** — 30 test cases ครอบคลุม 6 categories + regression tracking + HTML report
- **🔁 Resume Mode** — รัน validation แบบ checkpoint ได้ เมื่อชน rate limit ค่อยรันต่อ

---

## 🚀 Quickstart

### 1. ติดตั้ง

```powershell
# Clone และเข้าโฟลเดอร์
cd C:\Users\<you>\Desktop\TharmYa

# สร้าง venv (Windows)
python -m venv venv
.\venv\Scripts\Activate.ps1

# ลง dependencies
pip install -r requirements.txt
```

### 2. ตั้ง API Key

คัดลอก `.env.example` → `.env` แล้วเติม key ใน `.env` (โหลดอัตโนมัติผ่าน `python-dotenv` — ไม่ต้อง set `$env:VAR` ทุกครั้ง):

```powershell
Copy-Item .env.example .env
notepad .env   # ใส่ GEMINI_API_KEY หรือ OPENAI_API_KEY
```

ขอ key ฟรี:
- **Gemini** (แนะนำ): https://aistudio.google.com/apikey
- **OpenAI**: https://platform.openai.com/api-keys
- **OpenRouter** (proxy หลายโมเดล): https://openrouter.ai/keys

> 🔒 `.env` ถูก `.gitignore` แล้ว — secrets จะไม่ติด commit เผลอเข้า public repo

### 3. รัน web app

```powershell
python app.py
```

เปิด browser → **http://localhost:7860**

---

## 🧪 Validation

```powershell
# Phase 1: pre-check + RAG (ฟรี ไม่ต้องใช้ key)
python validation.py

# Phase 2: ครบ 30 cases กับ LLM จริง
python validation.py --full

# ถ้าชน rate limit ระหว่างทาง — รันต่อจากที่ค้าง
python validation.py --full --resume

# subset เพื่อ smoke-test
python validation.py --subset 6
```

ผลลัพธ์:
- `validation_results.json` — ข้อมูล raw
- `validation_report.html` — รายงานสวยงาม (เปิดใน browser)
- `validation_baseline.json` — baseline สำหรับ regression diff

ดูรายละเอียดที่ [USAGE.md](./USAGE.md)

---

## 🏗️ โครงสร้าง

```
TharmYa/
├── app.py                      # Gradio web app (entry point)
├── prompt_engine.py            # System prompt + safety pre-check
├── rag_engine.py               # TF-IDF retrieval + interaction checker
├── validation.py               # 30 test cases + evaluator + HTML report
├── thai_otc_drugs.json         # Drug knowledge base (25 ยา + red flags)
├── requirements.txt
├── .env.example                # Template (ไม่มี secret)
├── .gitignore                  # กัน .env / artifacts ติด git
├── README.md                   # ไฟล์นี้
├── USAGE.md                    # คู่มือใช้งานเต็ม
├── CHANGES.md                  # changelog
└── tests/
    ├── test_pre_check.py
    ├── test_rag_engine.py
    └── test_evaluator.py
```

---

## 🔧 เปลี่ยน Provider

ระบบ auto-detect จาก env var — ตั้งครั้งเดียวใน `.env`:

| Provider | env vars |
|---|---|
| **Gemini** (default) | `GEMINI_API_KEY=...` |
| **OpenAI** | `AI_PROVIDER=openai` + `OPENAI_API_KEY=sk-...` |
| **OpenRouter** | `AI_PROVIDER=openai` + `OPENAI_API_KEY=sk-or-...` + `OPENAI_BASE_URL=https://openrouter.ai/api/v1` + `OPENAI_MODEL=...` |
| **Groq** | `AI_PROVIDER=openai` + `OPENAI_API_KEY=gsk_...` + `OPENAI_BASE_URL=https://api.groq.com/openai/v1` + `OPENAI_MODEL=llama-3.3-70b-versatile` |
| **Ollama (local)** | `AI_PROVIDER=openai` + `OPENAI_API_KEY=anything` + `OPENAI_BASE_URL=http://localhost:11434/v1` + `OPENAI_MODEL=gemma3:12b` |

---

## 🧠 หลักการทำงาน (ภาพรวม)

```
User Input
   ↓
[pre_check_input]  ←─ safety guardrails (emergency / out-of-scope / prescription)
   ↓ (passed)
[RAG retrieve]     ←─ TF-IDF ดึงยา top-5 ที่ตรงอาการ
   ↓
[build_user_context]  ←─ รวมข้อมูลผู้ป่วย (อายุ, ยาที่กิน, โรค, ตั้งครรภ์)
   ↓
[LLM stream]       ←─ ส่ง: system_prompt + drug_context + user_context + question
   ↓
[render reply]     ←─ Streaming token-by-token ใน Gradio Chatbot
```


---

## ⚠️ Disclaimer

TharmYa AI เป็น**ข้อมูลประกอบการตัดสินใจ**เท่านั้น — ไม่ใช่การวินิจฉัยจากแพทย์
- หากอาการรุนแรงหรือไม่ดีขึ้นใน 2-3 วัน → ปรึกษาเภสัชกร/แพทย์
- เหตุฉุกเฉิน → **โทร 1669** (สายด่วนการแพทย์ฉุกเฉิน)

---

## 📄 License

โปรเจกต์การศึกษา — ใช้เพื่อการเรียนการสอน CS460 เท่านั้น
