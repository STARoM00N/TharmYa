# สรุปการปรับปรุง PharmaThai AI

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
