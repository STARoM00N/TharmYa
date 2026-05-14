# สรุปการปรับปรุง TharmYa AI

---

## 🆕 Session 2026-05 — UX/UI Overhaul + Validation Resume

### 🎨 `app.py` — UI สำหรับผู้สูงอายุ

- **Typography ใหม่ทั้งหน้า** — base font 18-20px, line-height 1.7, ฟอนต์ **Sarabun** (Thai-optimized) ผ่าน Google Fonts
- **Theme** — Soft theme (emerald/teal) สีสบายตา contrast สูง
- **Header ใหญ่ขึ้น** — h1 42px, gradient teal-emerald, shadow
- **"📋 วิธีใช้งานง่าย ๆ 3 ขั้นตอน" panel** — กล่องเขียวใต้ header อธิบายขั้นตอนแบบ numbered list
- **Quick-pick symptom buttons** — 5 ปุ่ม one-tap (ปวดหัว, เป็นไข้, ไอเจ็บคอ, ปวดท้อง, เป็นหวัด) — pre-fill textbox ให้แก้ก่อนส่ง
- **ปุ่มใหญ่ทุกตัว** — min-height 56px, font 20px, primary button สีเขียวเข้ม hover effect
- **Input fields** — font 20px, padding 14px, textarea 2 บรรทัด, label เด่นชัด
- **Checkbox** — ขยาย 22×22px
- **Disclaimer panel** — ขยายเนื้อหา + เพิ่มเบอร์ฉุกเฉิน **1669** เด่น

### 🛠️ Gradio 6 Compatibility Fixes

- ลบ `show_copy_button=True` จาก `gr.Chatbot(...)` (ถูกถอดใน Gradio 6 → `TypeError`)
- ลบ `bubble_full_width=False` (deprecated)
- ย้าย `theme=` จาก `gr.Blocks(...)` → `app.launch(...)` (Gradio 6 deprecation warning)
- เพิ่ม `APP_THEME` constant เพื่อ reuse

### 🧹 Chatbot Toolbar Cleanup

- `buttons=[]` บน `gr.Chatbot` → ปิด share + copy_all built-in
- เพิ่ม CSS rule ซ่อนปุ่ม clear/trash ที่ Gradio ยังเรนเดอร์อยู่ (ซ้ำกับปุ่ม "🗑️ ล้างและเริ่มใหม่" ที่ sidebar)
- ใช้ `elem_id="pharmathai-chatbot"` เพื่อให้ CSS target ได้แม่นยำ

### ✅ `validation.py` — Resume Support

แก้ปัญหา free-tier rate limit ทำให้รัน --full ไม่ครบ 30 cases รวด:

- **`--resume` CLI flag** ใหม่ — รันต่อจาก `validation_results.json` เดิม
- **`_load_prior_results()`** — โหลด JSON เดิม รื้อกลับเป็น in-memory shape (รวม TC fields + score fields) keyed by id
- **`_select_subset(exclude_ids=...)`** — รับ set ของ IDs ที่ทำแล้ว → subset selection ข้ามให้
- **Merge logic** ก่อน `print_summary` / `save_results` / `render_html_report` — รวมผลเก่า + ใหม่ เรียงตาม `_TC_ORDER` (TC01→TC30) → JSON/HTML สุดท้ายมีครบทุก case ไม่ว่าจะรันกี่รอบ
- **Errored cases auto-retry** — case ที่ reply ขึ้นต้น `[ERROR]` ไม่ถูกนับว่า done → resume รอบหน้าจะลองใหม่อัตโนมัติ
- **Early-exit fast path** — ถ้า resume แล้วไม่มี case ที่ยังต้องรัน → re-render report จากของเดิมและจบทันที (ไม่ต้องเรียก LLM)

**วิธีใช้:**
```powershell
python validation.py --full              # รอบแรก
python validation.py --full --resume     # ต่อจากที่ค้าง (ทำซ้ำได้)
python validation.py --subset 10 --resume   # รัน 10 case ที่ยังไม่ได้ทำ
```

### 🔐 `.env` Auto-loading (DX improvement)

ก่อนหน้านี้ต้อง `$env:VAR=...` ทีละตัวใน PowerShell ทุก session — น่าเบื่อและ leak ง่าย ตอนนี้:

- เพิ่ม `python-dotenv>=1.0,<2` ใน `requirements.txt`
- `app.py` และ `validation.py` มี `load_dotenv()` ที่หัวไฟล์ (wrap ด้วย try/except — ถ้าไม่มี dotenv lib ก็ไม่ crash)
- ตอน startup → อ่าน `.env` ในโฟลเดอร์โปรเจกต์ → ใส่เข้า `os.environ` อัตโนมัติ
- `.gitignore` กัน `.env` (ของจริง) ออกจาก git แล้ว — commit ได้ `.env.example` template เท่านั้น

**Workflow ใหม่:**
```powershell
Copy-Item .env.example .env
notepad .env             # เติม GEMINI_API_KEY=... ครั้งเดียว
python app.py            # ใช้งานได้เลย ไม่ต้อง set env ทุกครั้ง
```

### 📛 Branding

- รีเนม "PharmaThai" → "TharmYa" ในส่วน frontend (header, title, docstring เริ่มต้น)
- ฟังก์ชัน / log channels ภายในบางส่วนยังใช้ `pharmathai.*` (ไม่กระทบ user — รอ refactor ครั้งหน้า)

### 📚 Documentation

- **`README.md`** — เขียนใหม่จาก placeholder เป็น full project intro: features, quickstart, provider table, architecture diagram, disclaimer
- **`CHANGES.md`** — เพิ่ม section "Session 2026-05" นี้ (เก็บประวัติเดิมไว้)
- **`TharmYa_Concept.md`** (อยู่ที่ Desktop ไม่ใน repo) — เอกสารแยกอธิบายหลักการออกแบบ 5 ข้อ + architecture เชิงลึก + validation philosophy

---

# สรุปการปรับปรุง PharmaThai AI (เดิม)

## 🐛 แก้บั๊ก

### `rag_engine.py` — Regex tokenizer ขาดอักขระ
- บรรทัดเดิมใช้ `r'[...""'']+'` ซึ่ง Python ปิด raw string เร็วเกินไป → curly quotes ไม่ถูก split จริง
- เปลี่ยนเป็น `_PUNCT_SPLIT_RE` ที่ระบุ codepoint ชัดเจน (`“”‘’`)

### `app.py` — OpenAI ไม่รองรับ list-content จาก Gradio 6
- `_call_gemini` แปลง list → string แล้ว แต่ `_call_openai` ส่ง raw → OpenAI reject
- แยกเป็น helper `_to_text()` ใช้ร่วมกันทั้งสอง provider + ใช้ตอนรับ `user_message` ด้วย

### `validation.py` — `evaluate_response` นับ checkpoint ผิด
- มี `cp_keywords` dict สร้างไว้แต่**ไม่เคยถูกอ่าน** → fallback ไปใช้ `cp.split()` ทำให้คำธรรมดา ("ยา", "บอก") match ทุกครั้ง คะแนนสูงเกินจริง
- เขียนใหม่เป็น matcher registry (ดูด้านล่าง)

---

## 🛡️ Safety Hardening

### `prompt_engine.pre_check_input`
- เพิ่ม NFKC normalization + strip whitespace/punctuation ก่อน match
- `เ จ็ บ ห น้ า อ ก`, `เจ็บ-หน้า-อก`, `amoxi cillin` ไม่ bypass แล้ว
- Logging ผ่าน logger `pharmathai.safety` (emergency = WARNING, prescription = INFO)
- สลับลำดับ: prescription check ก่อน out-of-scope (เคสร้ายแรงกว่ามาก่อน)
- เพิ่ม field `matched` ใน return dict เพื่อ debug ง่ายขึ้น

---

## 🎨 UX (`app.py`)

- **Streaming response** — ทั้ง Gemini และ OpenAI ผ่าน `stream_llm()` (yield ข้อความสะสมไปเรื่อย ๆ)
- **RAG Panel** — Accordion แสดงยาที่ระบบดึงมาให้ AI พิจารณา + คะแนน relevance + drug interactions แบบ real-time (โปร่งใส ผู้ใช้เห็นเหตุผลเบื้องหลัง)
- เพิ่ม `gr.Chatbot(type="messages")` รองรับ Gradio 6
- Logger setup ที่ startup, ปรับ level ผ่าน env `PHARMATHAI_LOG_LEVEL`

---

## ✅ Validation Upgrade (`validation.py`)

### `evaluate_response` เขียนใหม่
- **Drug alias resolution** — โหลดจาก `thai_otc_drugs.json`: `Paracetamol` ⇄ `พาราเซตามอล` ⇄ `Sara`/`Panadol`
- **Safety check** ขยาย context window จาก 30 → 80 ตัวอักษร (Thai sentences ยาวกว่านั้น) + เพิ่ม guard words (`เสี่ยง`, `ไม่แนะนำ`, `งด`)
- **Checkpoint matchers** — registry ของ phrase → predicate (เช่น `ขนาดยา` → check regex `\d+ mg`, `1669` → check 1669/ฉุกเฉิน, `ห้าม Ibuprofen` → check warning context)
- คืนค่าเพิ่ม: `drugs_found`, `drugs_missing`, `checkpoint_details` (per-checkpoint pass/fail)

### Artifacts ใหม่
| ไฟล์ | คำอธิบาย |
|---|---|
| `validation_results.json` | ผลล่าสุด (รายละเอียดครบ checkpoint) |
| `validation_baseline.json` | snapshot ที่ promote ไว้เป็นจุดเปรียบเทียบ |
| `validation_report.html` | รายงาน HTML แบบ self-contained (ไม่ต้องมี internet) |

### Regression tracking
```bash
python3 validation.py --full              # รัน LLM phase
python3 validation.py --promote-baseline  # freeze ผลปัจจุบันเป็น baseline
python3 validation.py --full              # รอบถัดไป → print diff vs baseline
```
ผลที่ได้แสดง: 🟢 newly passing / 🔴 newly failing / 🟡 persistent failures + delta % ของ pass rate / safety / accuracy

---

## 🧪 Tests (`tests/`)

49 test cases ใน 3 ไฟล์ — รันใน venv เปล่าใช้เวลา **40 ms**:

| ไฟล์ | ครอบคลุม |
|---|---|
| `test_pre_check.py` | bypass attempts (spaces/punct/case), all 3 statuses, edge cases |
| `test_rag_engine.py` | tokenizer (typographic quotes regression), retrieval relevance, interaction detection, severity |
| `test_evaluator.py` | alias resolution, safety guard logic, checkpoint matchers, overall scoring |

```bash
pip install -r requirements.txt
pytest tests/ -v
```

---

## 📦 ไฟล์เพิ่ม

- `requirements.txt` — bounded versions ของ gradio/google-generativeai/openai/pytest
- `tests/test_pre_check.py`, `tests/test_rag_engine.py`, `tests/test_evaluator.py`

## 🗑️ ไฟล์ที่ลบโดยไม่ตั้งใจ

- `CS460 - Project.pdf` — ขอโทษนะครับ คำสั่ง cleanup `rm -f CS460*.pdf` ของผมกว้างเกินไป ไฟล์นี้ไม่ได้เข้า trash (`rm -f` ข้าม) ถ้ามีสำรองที่ Mac/iCloud ก็ copy กลับมาได้
