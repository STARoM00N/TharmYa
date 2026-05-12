# คู่มือใช้งาน PharmaThai AI

## 📦 ติดตั้ง

```bash
cd /home/siwakorn/backup/phamathai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 🔑 ตั้ง API Key

เลือกอย่างใดอย่างหนึ่ง — ระบบ auto-detect:

```bash
# แบบที่ 1: Gemini (แนะนำ — มี free tier)
export GEMINI_API_KEY='your-key'

# แบบที่ 2: OpenAI
export AI_PROVIDER=openai
export OPENAI_API_KEY='your-key'
```

ขอ key ได้จาก:
- Gemini: https://aistudio.google.com/apikey
- OpenAI: https://platform.openai.com/api-keys

---

## 🚀 วิธีใช้ — Web App

### เริ่ม server

```bash
python3 app.py
```

เปิด browser ไปที่ **http://localhost:7860**

### หน้าตา app

| ส่วน | หน้าที่ |
|---|---|
| 💬 Chatbot (ซ้าย) | สนทนากับ "ภูมิ" — พิมพ์อาการ → ได้คำแนะนำยา |
| 🔬 RAG Retrieval (Accordion ใต้ chat) | ดูว่าระบบดึงยาตัวไหนมาให้ AI พิจารณา + คะแนน relevance |
| 👤 Patient Profile (ขวา) | กรอกอายุ / ยาที่กินอยู่ / โรคประจำตัว / ตั้งครรภ์ |

### ตัวอย่างการถาม

| สิ่งที่พิมพ์ | สิ่งที่ได้ |
|---|---|
| `ปวดหัวมาก ไม่มีไข้` | แนะนำ Paracetamol/Ibuprofen + ขนาด + ราคา |
| `ปวดหัว` + meds=`Warfarin` | แนะนำ Paracetamol + เตือน "ห้าม NSAIDs" |
| `เจ็บหน้าอกแน่นมาก` | 🚨 ตัด short-circuit → บอกโทร 1669 (ไม่เรียก LLM) |
| `อยากกิน Amoxicillin` | ปฏิเสธ — ต้องมีใบสั่งแพทย์ |
| `แนะนำร้านอาหาร` | ปฏิเสธ — นอกขอบเขต |

### วิธีดูผลในหน้า app

1. **Chatbot** — คำตอบ AI streaming token-by-token
   - มีหัวข้อ: 🩺 ประเมินอาการ → 💊 ยาที่แนะนำ → ⚠️ คำเตือน → 🏥 ควรพบแพทย์ถ้า → 💡 คำแนะนำเพิ่มเติม
2. **RAG Panel (กดเปิด accordion)** — ดูว่าทำไม AI ตอบแบบนั้น
   - แสดงยาทุกตัวที่ retrieve มาพร้อม `score 0.00–1.00` (สูง = ตรงอาการมาก)
   - ถ้ามี drug interaction → 🚫 alert พร้อมระดับความรุนแรง (HIGH/MODERATE)

---

## 🧪 วิธีรัน Validation (ทดสอบคุณภาพ AI)

### Phase 1: ทดสอบ local (ฟรี ไม่ต้องใช้ API)

```bash
python3 validation.py
```

ทดสอบ:
- **Pre-check** — guardrail ก่อนถึง LLM (30 cases)
- **RAG retrieval** — ระบบดึงยาตรงอาการไหม

### Phase 2: ทดสอบเต็ม (ต้องมี API key)

```bash
python3 validation.py --full
```

รัน 30 test cases กับ LLM จริง — ใช้เวลา ~5 นาที (มี `time.sleep(1)` ระหว่าง call เพื่อกัน rate limit)

### วิธีดูผล

หลังรัน `--full` จะได้ 2 ไฟล์:

#### 1. Terminal Output

```
============================================================
VALIDATION SUMMARY
============================================================
Total test cases     : 30
Overall pass rate    : 28/30 (93.3%)
Average accuracy     : 87.5%
Safety compliance    : 30/30 (100.0%)
Checkpoints met      : 78/90 (86.7%)

Category         Pass  Total     Rate   Safety
--------------------------------------------------
edge_case           1      2      50%     100%
emergency           5      5     100%     100%
interaction         5      6      83%     100%
normal             10     10     100%     100%
out_of_scope        2      2     100%     100%
vulnerable          5      5     100%     100%

✅ No safety violations detected
```

**สิ่งที่ต้องดู:**
- 🔴 **Safety compliance < 100%** = ปัญหาใหญ่ — AI แนะนำยาอันตราย (ดู `🚨 CRITICAL SAFETY FAILURES`)
- 🟡 **Accuracy < 70%** = AI ไม่แนะนำยาที่ควรแนะนำ
- 🟢 **Checkpoints < 80%** = AI ไม่ได้ใส่ข้อมูลครบ (เช่น ลืมบอกราคา/ขนาด)

#### 2. `validation_report.html`

```bash
xdg-open validation_report.html
```

หน้ารายงานมี:
- 📊 Summary cards (4 ตัวเลขหลัก)
- 📋 ตาราง 30 cases — กด `detail` แต่ละแถวเพื่อดู:
  - ยาที่คาดหวัง vs ที่ AI แนะนำจริง
  - Checkpoint ไหนผ่าน/ไม่ผ่าน
  - Reply เต็มของ AI

#### 3. `validation_results.json`

ข้อมูล raw — ใช้ทำกราฟ/วิเคราะห์ต่อได้

---

## 📈 Regression Tracking (เปรียบเทียบกับครั้งก่อน)

### ตั้ง baseline (ทำครั้งเดียว)

หลังรัน `--full` ครั้งแรกแล้วผลออกมาดี:

```bash
python3 validation.py --promote-baseline
```

ระบบจะ copy `validation_results.json` → `validation_baseline.json`

### วัด regression ครั้งถัดไป

```bash
python3 validation.py --full
```

จะมี section ใหม่เพิ่มขึ้นมา:

```
============================================================
REGRESSION vs baseline (2026-05-10 14:30:00, gemini/gemini-2.5-flash)
============================================================
Overall pass rate : +3.3%
Safety compliance : +0.0%
Average accuracy  : +5.2%
🟢 Newly passing      : TC14, TC26
🔴 Newly failing      : TC22
🟡 Persistent failures: TC30
```

**วิธีอ่าน:**
- 🟢 Newly passing = case ที่เคยพังแล้วฟิกซ์ได้
- 🔴 Newly failing = **regression** ต้องไปดูว่าทำไมพัง (เปิด HTML report → click `detail` ของ case นั้น)
- 🟡 Persistent failures = พังตั้งแต่ baseline แล้ว — เป้าหมาย iteration ถัดไป
- delta % บอก trend รวม

---

## 🛠️ วิธีรัน Unit Tests

```bash
pytest tests/ -v
```

ใช้เวลา ~40ms — ทดสอบ pre_check (bypass cases), RAG engine (tokenizer, retrieval, interactions), evaluator (alias resolution, safety logic)

ใช้ตอนเขียนโค้ดเพิ่ม — รันก่อน commit เพื่อกัน regression

---

## 🔧 Workflow แนะนำเวลาปรับปรุง

```bash
# 1. แก้โค้ด (เพิ่มยาใหม่ / ปรับ prompt / เพิ่ม keyword)
vim thai_otc_drugs.json

# 2. รัน unit tests กัน regression
pytest tests/ -v

# 3. รัน validation เต็มดูคะแนนรวม
python3 validation.py --full

# 4. เปิด HTML report ดูราย case
xdg-open validation_report.html

# 5. ถ้าผลดีขึ้น → freeze เป็น baseline ใหม่
python3 validation.py --promote-baseline
```

---

## 🆘 Troubleshooting

| ปัญหา | สาเหตุที่เป็นไปได้ | วิธีแก้ |
|---|---|---|
| `ModuleNotFoundError: gradio` | ไม่ได้ activate venv | `source .venv/bin/activate` |
| `❌ NOT SET` API key ตอน startup | env var ไม่ได้ตั้ง | `export GEMINI_API_KEY=...` |
| Streaming ไม่ทำงาน | google-generativeai เก่ากว่า 0.7 | `pip install -U google-generativeai` |
| Validation ค้าง | rate limit | เพิ่ม `time.sleep(2)` ใน `run_llm_tests` |
| RAG ไม่เจอยา | คำในอาการไม่ตรง symptoms_treated | เพิ่ม keyword ใน `thai_otc_drugs.json` |

---

## 📁 โครงสร้างไฟล์

```
phamathai/
├── app.py                      # Gradio web app (entry point)
├── prompt_engine.py            # System prompt + safety pre-check
├── rag_engine.py               # TF-IDF retrieval + interaction checker
├── validation.py               # 30 test cases + evaluator + reports
├── thai_otc_drugs.json         # Drug knowledge base (25 ยา + red flags)
├── requirements.txt            # Python deps
├── CHANGES.md                  # สรุปการปรับปรุง
├── USAGE.md                    # ไฟล์นี้
└── tests/
    ├── test_pre_check.py
    ├── test_rag_engine.py
    └── test_evaluator.py
```

หลังรัน validation จะเพิ่ม:
```
├── validation_results.json     # ผลล่าสุด
├── validation_baseline.json    # baseline สำหรับ regression diff
└── validation_report.html      # รายงาน HTML
```
