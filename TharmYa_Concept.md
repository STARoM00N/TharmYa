# 💊 TharmYa AI — หลักการและแนวคิดของโปรเจกต์

> เอกสารอธิบาย **ทำไม** ออกแบบแบบนี้ — ไม่ใช่ **ทำอะไร** (อันนั้นอยู่ใน README/USAGE)

CS460 Artificial Intelligence | Final Project

---

## 🎯 ปัญหาที่กำลังแก้

คนไทยจำนวนมาก **ซื้อยาเอง** จากร้านขายยาโดยไม่ได้ปรึกษาเภสัชกรเพราะเขิน/รีบ/ไม่มีเวลา

ความเสี่ยงที่เกิด:
1. **ใช้ยาผิดอาการ** — กินยาแก้ปวดทั่วไปทั้งที่เป็นอาการเตือนของ heart attack
2. **Drug interaction** — กิน NSAIDs ทับ Warfarin → เลือดออก
3. **ใช้ในกลุ่มเสี่ยง** — คนท้อง / เด็ก / ผู้สูงอายุ กินยาที่ห้ามใช้
4. **ใช้ยาที่ต้องสั่งโดยแพทย์** — ซื้อยาปฏิชีวนะมากินเอง → ดื้อยา

**Pain point ที่จริง:** ผู้ใช้ไม่รู้ว่าตัวเองไม่รู้ — ถามอาจารย์ Google ได้คำตอบที่ไม่ปรับตาม context ของตัวเอง

**Insight ของโปรเจกต์นี้:** AI ที่ดีต้องไม่ใช่แค่ตอบเก่ง — ต้อง **รู้ว่าเมื่อไหร่ไม่ควรตอบ** (refusal เป็น feature ไม่ใช่ bug)

---

## 🧠 หลักการออกแบบ 5 ข้อ

### 1. Safety > Helpfulness

ทุก request ผ่าน **pre-check guardrail ก่อนถึง LLM**:

```
User → pre_check_input() → {EMERGENCY | OUT_OF_SCOPE | PRESCRIPTION | OK}
                            ↓ EMERGENCY → ตัดทาง LLM ทันที, บอกโทร 1669
                            ↓ OUT_OF_SCOPE → ปฏิเสธสุภาพ
                            ↓ PRESCRIPTION → บอกว่าต้องพบแพทย์
                            ↓ OK → ส่งเข้า RAG + LLM
```

**ทำไมต้อง pre-check ก่อน LLM ไม่ใช่ใน LLM:**
- LLM อาจ "เผลอ" ตอบเคสฉุกเฉินด้วยคำแนะนำที่ไม่ทันการ — เสียชีวิตได้
- Regex/keyword match deterministic 100% — ทดสอบได้, audit ได้
- เร็วกว่าและถูกกว่า — ไม่ต้องเสีย token เรียก LLM สำหรับเคสที่รู้คำตอบอยู่แล้ว
- Bypass attacks ป้องกันได้แม่นกว่า — NFKC normalize + strip spaces ก่อน match (ผู้ใช้พิมพ์ `เ จ็ บ ห น้ า อ ก` หลบไม่ได้)

### 2. RAG > Fine-tuning

เลือก **Retrieval-Augmented Generation** เพราะข้อมูลยา/ราคา/availability เปลี่ยนบ่อย:

| Approach | Update คอสต์ | Hallucination | Token / call |
|---|---|---|---|
| Fine-tune | retrain ทั้ง model | สูง | สั้น |
| **RAG** | แก้ JSON file | **ต่ำ** (LLM เห็นข้อมูลจริง) | **2K (top-5 ยา)** |
| All-in-context | $0 | ต่ำ | 12K (25 ยา) |

**Token saving จาก RAG เห็นชัดมากตอน validation:**
- ก่อนใส่ RAG → ทุก call ส่ง knowledge base ทั้ง 25 ยา → Gemini free TPM หมดใน ~5 cases
- หลังใส่ RAG → ส่ง top-5 ที่ตรงอาการ → รัน ~21 cases ได้ก่อนเจอ limit

### 3. Transparency เป็น UX feature

หน้า web app มี **🔬 RAG Retrieval Accordion** ที่กดเปิดเพื่อดู:
- ยาตัวไหนถูก retrieve มาให้ AI พิจารณา
- คะแนน relevance (0.00-1.00)
- คำใน input ที่ match
- Drug interaction warnings ที่ระบบเจอ

**ทำไม:** ผู้ใช้ที่เห็นเหตุผลเบื้องหลังจะ **ไม่เชื่อ AI 100%** — แต่ใช้เป็นข้อมูลประกอบการตัดสินใจ (ตรงกับ disclaimer)

ในงานวิจัย explainable AI: transparency ช่วยปรับ trust calibration — ผู้ใช้ที่เข้าใจระบบจะรู้ว่าเมื่อไหร่ควรเชื่อ เมื่อไหร่ควรถามต่อ

### 4. UI ออกแบบสำหรับ "คนที่กลัวเทคโนโลยี"

target user หลักของ TharmYa คือ **ผู้สูงอายุ + คนต่างจังหวัด** ที่ซื้อยาเองบ่อย:

| Design decision | เหตุผล |
|---|---|
| Font 18-20px base | สายตาผู้สูงอายุ |
| Quick-pick symptom buttons | ไม่ต้องพิมพ์ — แตะปุ่ม |
| "📋 วิธีใช้ 3 ขั้นตอน" panel | คนที่ไม่คุ้น chatbot ต้องการ scaffold |
| ฟอนต์ Sarabun | Thai-readable, ไม่ใช่ Helvetica/Arial |
| ปุ่ม min-height 56px | นิ้วใหญ่ / มือสั่น แตะได้ |
| สี contrast สูง (Soft theme + emerald) | ผู้สูงอายุ contrast sensitivity ลด |
| Disclaimer + 1669 visible ตลอด | ไม่ซ่อนใน accordion |

**ไม่ใช้:** dark mode, animations เยอะ, jargon ภาษาอังกฤษ

### 5. Provider-agnostic by env vars

โค้ดไม่ผูกกับ Gemini หรือ OpenAI ตัวใดตัวหนึ่ง — ใช้ **OpenAI-compatible API standard**:

```python
# app.py / validation.py auto-detect:
if AI_PROVIDER == "openai":  # ครอบคลุม OpenRouter, Groq, Cerebras, Ollama
    ...
else:
    use_gemini()
```

**ประโยชน์:**
- เปลี่ยน provider โดยไม่ต้องแก้ code → แก้แค่ env vars
- A/B test คุณภาพข้าม providers ได้ง่าย
- รัน local ผ่าน Ollama ได้ฟรี (ตอน demo offline)
- ป้องกัน vendor lock-in

---

## 🏛️ Architecture แบบ End-to-End

```
┌──────────────────────────────────────────────────────────────┐
│  Gradio Web UI (app.py)                                      │
│  - Chatbot (streaming)                                       │
│  - Patient profile inputs                                    │
│  - RAG transparency panel                                    │
│  - Quick-pick buttons                                        │
└────────────────┬─────────────────────────────────────────────┘
                 │ user_message + history + patient_info
                 ▼
┌──────────────────────────────────────────────────────────────┐
│  pharmathai_chat() orchestrator                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Step 1: pre_check_input(user_message)                 │  │
│  │    └→ EMERGENCY/OUT_OF_SCOPE/PRESCRIPTION → return     │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Step 2: rag.retrieve_and_augment()                    │  │
│  │    - TF-IDF score ยาทุกตัวกับ user query               │  │
│  │    - Top-5 ที่คะแนนสูงสุด                              │  │
│  │    - Check drug interactions vs patient.current_meds   │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Step 3: build_user_context_prompt()                   │  │
│  │    - รวม age, current_meds, conditions, is_pregnant    │  │
│  │    - Format เป็น structured prompt section             │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Step 4: stream_llm() — provider-agnostic dispatch     │  │
│  │    - Gemini: google-generativeai SDK                   │  │
│  │    - OpenAI-compatible: openai SDK + OPENAI_BASE_URL   │  │
│  │    - Stream tokens cumulative → UI                     │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## ✅ Validation Philosophy

โปรเจกต์มี **30 test cases ใน 6 categories**:

| Category | จำนวน | วัดอะไร |
|---|---|---|
| Normal symptoms | 10 | accuracy + completeness |
| Drug interactions | 6 | คาดการณ์ปฏิกิริยายาได้ไหม |
| Emergency red flags | 5 | ตัด short-circuit ถูกหรือไม่ |
| Vulnerable groups | 5 | ปรับคำแนะนำตามอายุ/ตั้งครรภ์/โรคประจำตัว |
| Out-of-scope | 2 | ปฏิเสธอย่างสุภาพ |
| Edge cases | 2 | ข้อมูลไม่พอ / อาการซับซ้อน |

**4 metrics ที่ track:**

1. **Accuracy Score** — ยาที่แนะนำตรงกับ expected ไหม (alias-aware: `Paracetamol` ⇄ `พาราเซตามอล` ⇄ `Sara`)
2. **Safety Score** — ไม่แนะนำยาที่ห้าม (false negative = critical failure)
3. **Interaction Detection Rate** — ตรวจจับ drug interaction ได้
4. **Guardrail Compliance** — ปฏิเสธอย่างถูกต้องเมื่อควรปฏิเสธ

**Regression tracking:** snapshot ผลครั้งล่าสุดเป็น `validation_baseline.json` → ครั้งถัดไป diff เทียบให้เห็น 🟢 newly passing / 🔴 newly failing / 🟡 persistent failures

---

## 🎓 Why This Project Matters (สำหรับเกรด)

- **Real-world problem** — pain point จริงในสังคมไทย ไม่ใช่ toy problem
- **Technical depth** — RAG + TF-IDF + multi-provider abstraction + streaming + safety pre-check
- **Evaluation rigor** — validation framework + regression tracking + 49 unit tests
- **Production-grade UX** — ใช้ได้จริงโดยผู้สูงอายุ ไม่ใช่ developer UI
- **Reproducible** — env vars, gitignore, requirements, baseline → คนอื่นรันต่อได้

---

## 🚧 ข้อจำกัด (acknowledged)

- **Knowledge base ขนาดเล็ก** — 25 ยา ไม่ครอบคลุมทุกอาการ (extend ได้ผ่าน JSON)
- **ไม่มี database จริงของผู้ป่วย** — ข้อมูลผู้ใช้ session-only (privacy by design)
- **LLM hallucination risk** — RAG ลดได้แต่ไม่ขจัด → disclaimer สำคัญมาก
- **Thai NLP simple** — TF-IDF ไม่ใช้ Thai word segmentation library → คำผสมอาจ tokenize ผิด (trade-off: dependency-light)

---

## 📚 อ้างอิงที่ใช้

- **Gemini API** — https://ai.google.dev
- **OpenAI Compatibility Spec** — https://platform.openai.com/docs/api-reference
- **Gradio Components** — https://www.gradio.app/docs
- **TF-IDF** — Manning, Raghavan, Schütze, "Introduction to Information Retrieval"
- **Thai OTC drug data** — สำนักงานคณะกรรมการอาหารและยา (อย.)

---

_เอกสารนี้สรุปเฉพาะ **หลักการ** ของโปรเจกต์ — ไม่ใช่คู่มือใช้งาน (ดู `README.md`/`USAGE.md` ในโฟลเดอร์โปรเจกต์)_
