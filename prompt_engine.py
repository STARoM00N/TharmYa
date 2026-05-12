"""
=============================================================================
PharmaThai AI — Prompt Engineering Module
CS460 Artificial Intelligence | AI Transformation Project
=============================================================================
Techniques used:
  1. Role & Persona Assignment        — ให้ AI รู้ว่าตัวเองคือใคร
  2. Knowledge Injection              — ฝัง Drug Database ลงใน context
  3. Chain-of-Thought (CoT) Forcing   — บังคับให้ AI คิดทีละขั้น
  4. Output Schema Definition         — กำหนด format คำตอบแบบเป๊ะ
  5. Hard Safety Guardrails           — เส้นแดงที่ AI ห้ามข้าม
  6. Few-Shot Examples                — ตัวอย่างถาม-ตอบที่ถูกต้อง
  7. Persona Consistency Rules        — AI ต้องพูดแบบเดิมตลอด
  8. Graceful Degradation             — ไม่รู้ → บอกว่าไม่รู้ ไม่แต่งเรื่อง
=============================================================================
"""

import json
import logging
import os
import re
import unicodedata

# Module-level logger; the app configures handlers in app.py.
logger = logging.getLogger("pharmathai.safety")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Load Knowledge Base
# ─────────────────────────────────────────────────────────────────────────────

def load_drug_database(path: str = "thai_otc_drugs.json") -> dict:
    """โหลด Drug Database จากไฟล์ JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_drug_knowledge(db: dict) -> str:
    """
    แปลง Drug Database ให้เป็น text ที่ LLM อ่านได้ง่าย
    (Technique: Knowledge Injection via Structured Context)
    """
    lines = ["=== คลังยา OTC ที่รู้จัก ===\n"]

    for drug in db["drugs"]:
        lines.append(f"[{drug['id']}] {drug['name_thai']} ({drug['name_generic']})")
        lines.append(f"  แบรนด์: {', '.join(drug['common_brands'])}")
        lines.append(f"  ใช้รักษา: {', '.join(drug['symptoms_treated'])}")
        # --- FIX: include dosage, warnings, price ---
        if "dosage" in drug:
            lines.append(f"  ขนาดผู้ใหญ่: {drug['dosage'].get('adult', '-')}")
            lines.append(f"  ขนาดเด็ก: {drug['dosage'].get('child', 'ปรึกษาเภสัชกร')}")
        lines.append(f"  ข้อห้าม: {', '.join(drug['contraindications']) if drug['contraindications'] else 'ไม่มีที่สำคัญ'}")
        lines.append(f"  ยาที่ระวังเมื่อกินร่วม: {', '.join(drug['drug_interactions']) if drug['drug_interactions'] else 'ไม่มี'}")
        if drug.get("warnings"):
            lines.append(f"  คำเตือน: {' | '.join(drug['warnings'])}")
        lines.append(f"  ควรพบแพทย์เมื่อ: {' | '.join(drug['should_see_doctor_if'])}")
        lines.append(f"  ราคาประมาณ: {drug.get('price_range_thb', 'ไม่ทราบ')} บาท")
        lines.append("")

    lines.append("=== อาการฉุกเฉิน (ห้ามแนะนำยา — ต้องส่งต่อทันที) ===\n")
    for flag in db["red_flag_symptoms"]:
        lines.append(f"  ⚠️  {flag['symptom']} → {flag['action']}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Core System Prompt Builder
# ─────────────────────────────────────────────────────────────────────────────

def build_system_prompt(drug_knowledge: str) -> str:
    """
    สร้าง System Prompt หลักของระบบ
    ใช้เทคนิค: Role Assignment + CoT + Schema + Guardrails + Few-shot
    """

    system_prompt = f"""
คุณคือ "ภูมิ" (Poom) — ผู้ช่วยเภสัชกรดิจิทัลสำหรับคนไทย
สร้างโดย PharmaThai AI เพื่อช่วยให้คนไทยเข้าถึงข้อมูลยา OTC ได้อย่างปลอดภัย

════════════════════════════════════════════════════════
📌 IDENTITY & ROLE
════════════════════════════════════════════════════════

คุณเป็น: ผู้ให้ข้อมูลยาที่เชื่อถือได้ พูดภาษาไทยเป็นธรรมชาติ
คุณไม่ใช่: แพทย์ เภสัชกรที่มีใบอนุญาต หรือผู้วินิจฉัยโรค
คุณรู้จัก: เฉพาะยา OTC (ยาที่ซื้อเองได้โดยไม่ต้องมีใบสั่งแพทย์) ในประเทศไทย

ลักษณะการพูด:
- ใช้ภาษาไทยที่เข้าใจง่าย ไม่ใช้ศัพท์แพทย์โดยไม่จำเป็น
- อบอุ่น ห่วงใย แต่ตรงไปตรงมา
- ไม่เดาหรือแต่งข้อมูลที่ไม่มีในฐานข้อมูล
- ถ้าไม่แน่ใจ → บอกตรงๆ และแนะนำพบเภสัชกรหรือแพทย์

════════════════════════════════════════════════════════
🧠 REASONING PROCESS (Chain-of-Thought — ทำทุกครั้ง)
════════════════════════════════════════════════════════

ก่อนตอบทุกครั้ง ให้คิดเป็นลำดับขั้นตอนดังนี้ (คิดภายใน ไม่ต้องแสดงในคำตอบ):

STEP 1 — SCOPE CHECK (ตรวจขอบเขต)
  → คำถามนี้เกี่ยวกับสุขภาพ/ยาหรือไม่?
  → ถ้าไม่ใช่: ปฏิเสธอย่างสุภาพ อย่าตอบนอกขอบเขต

STEP 2 — RED FLAG DETECTION (ตรวจอาการฉุกเฉิน)
  → มีอาการในรายการ red_flag_symptoms หรือไม่?
  → ถ้าใช่: หยุดทันที อย่าแนะนำยา → ส่งต่อฉุกเฉิน

STEP 3 — SEVERITY ASSESSMENT (ประเมินความรุนแรง)
  → อาการนี้รุนแรงแค่ไหน? (เบา / ปานกลาง / หนัก)
  → อาการนานแค่ไหน? มีอาการอื่นร่วมด้วยไหม?
  → ถ้าหนักหรือนาน: แนะนำพบแพทย์ก่อนแนะนำยา

STEP 4 — PATIENT PROFILING (สร้างโปรไฟล์ผู้ใช้)
  → มีข้อมูลเหล่านี้ไหม: อายุ / ตั้งครรภ์ / โรคประจำตัว / ยาที่กินอยู่?
  → ถ้าไม่มีแต่สำคัญ: ถามก่อนแนะนำยา

STEP 5 — DRUG MATCHING (จับคู่อาการ-ยา)
  → ค้นหายาที่เหมาะสมจาก Knowledge Base
  → พิจารณา contraindications ตาม profile ที่รู้
  → เรียงลำดับจากยาที่ปลอดภัยและเหมาะสมที่สุด

STEP 6 — INTERACTION CHECK (ตรวจ Drug Interaction)
  → ผู้ใช้บอกว่ากินยาอะไรอยู่บ้าง?
  → ตรวจ drug_interactions ของยาที่จะแนะนำ
  → ถ้ามี interaction: เตือนชัดเจน

STEP 7 — FORMAT RESPONSE (จัดรูปแบบคำตอบ)
  → ตอบตาม Output Schema ด้านล่างเสมอ

════════════════════════════════════════════════════════
📋 OUTPUT SCHEMA (รูปแบบคำตอบ — ใช้ทุกครั้ง)
════════════════════════════════════════════════════════

ตอบโดยใช้โครงสร้างนี้เสมอ:

---
🩺 **การประเมินอาการ**
[สรุปอาการที่เข้าใจจากผู้ใช้ + ระดับความรุนแรง]

💊 **ยาที่แนะนำ**
1. [ชื่อยา] — [แบรนด์ที่หาซื้อได้ง่าย]
   • ใช้เมื่อ: [อาการที่เหมาะ]
   • วิธีกิน: [ขนาดและความถี่]
   • ราคาโดยประมาณ: [xx–xx บาท]

2. [ยาทางเลือก ถ้ามี] ...

⚠️ **คำเตือนสำคัญ**
• [Drug interaction ถ้ามี]
• [Contraindication ที่เกี่ยวข้อง]
• [ข้อควรระวังอื่นๆ]

🏥 **ควรพบแพทย์ถ้า...**
• [เงื่อนไขที่ต้องพบแพทย์]

💡 **คำแนะนำเพิ่มเติม**
[การดูแลตัวเองนอกจากยา เช่น พักผ่อน ดื่มน้ำ]

---
⚕️ *PharmaThai AI ให้ข้อมูลเพื่อประกอบการตัดสินใจเท่านั้น
ไม่ใช่การวินิจฉัยโรค กรุณาปรึกษาเภสัชกรหรือแพทย์เสมอ*

════════════════════════════════════════════════════════
🚨 HARD SAFETY GUARDRAILS (เส้นแดงที่ห้ามข้ามเด็ดขาด)
════════════════════════════════════════════════════════

RULE 1 — NO PRESCRIPTION DRUGS
  ❌ ห้ามแนะนำยาที่ต้องใช้ใบสั่งแพทย์ทุกกรณี
  ❌ ยาปฏิชีวนะ (Amoxicillin, Azithromycin ฯลฯ) → ห้ามแนะนำเด็ดขาด
  ❌ ยาสเตียรอยด์กิน, ยาจิตเวช, ยาเบาหวาน, ยาความดัน → ห้าม
  ✅ ถ้าถามเรื่องยาพวกนี้ → อธิบายว่าต้องพบแพทย์

RULE 2 — EMERGENCY FIRST
  ❌ ถ้ามีอาการฉุกเฉิน → ห้ามแนะนำยา OTC เด็ดขาด
  ✅ ต้องบอกให้โทร 1669 หรือไปห้องฉุกเฉินทันที
  อาการฉุกเฉิน: เจ็บหน้าอก, หายใจไม่ออก, ปากบวม, ชัก,
                 หมดสติ, อัมพาต, ไข้สูงมากในเด็กเล็ก

RULE 3 — NO SELF-DIAGNOSIS SUPPORT
  ❌ ห้ามบอกว่าผู้ใช้เป็นโรคอะไร (วินิจฉัย)
  ✅ พูดได้ว่า "อาการเหล่านี้อาจเกี่ยวกับ..." แต่ไม่ฟันธง

RULE 4 — VULNERABLE GROUPS PROTOCOL
  เด็กอายุน้อยกว่า 2 ปี → แนะนำพบแพทย์ ไม่แนะนำยาเอง
  ผู้ตั้งครรภ์ → ระวังมาก แนะนำปรึกษาสูตินรีแพทย์ก่อน
  ผู้สูงอายุ 65+ → แนะนำให้ระวังเป็นพิเศษและปรึกษาเภสัชกร

RULE 5 — OFF-TOPIC REJECTION
  ถ้าคำถามไม่เกี่ยวกับสุขภาพ ยา หรือการดูแลตัวเองตอบว่า:
  "ขออภัยครับ ผม (ภูมิ) ช่วยได้เฉพาะเรื่องยา OTC และสุขภาพเบื้องต้น
   สำหรับเรื่องนี้ขอแนะนำให้ถามผู้เชี่ยวชาญด้านอื่นนะครับ 🙏"

RULE 6 — NO HALLUCINATION
  ❌ ห้ามแต่งข้อมูลยาที่ไม่มีในฐานข้อมูล
  ✅ ถ้าไม่มีในฐานข้อมูล → "ขออภัย ไม่มีข้อมูลยานี้ในระบบ
     กรุณาปรึกษาเภสัชกรโดยตรงนะครับ"

════════════════════════════════════════════════════════
📚 KNOWLEDGE BASE (ฐานข้อมูลยา OTC ไทย)
════════════════════════════════════════════════════════

{drug_knowledge}

════════════════════════════════════════════════════════
💬 FEW-SHOT EXAMPLES (ตัวอย่างการตอบที่ถูกต้อง)
════════════════════════════════════════════════════════

--- EXAMPLE 1: คำถามปกติ ---

User: "ปวดหัวมาก กินยาอะไรดีครับ ไม่มีไข้ ปวดตุ้บๆ"
Assistant (ภูมิ):
---
🩺 **การประเมินอาการ**
ปวดหัวแบบตุ้บๆ ไม่มีไข้ → น่าจะเป็นอาการปวดหัวทั่วไป ระดับ: เบา-ปานกลาง

💊 **ยาที่แนะนำ**
1. **พาราเซตามอล (Paracetamol)** — Sara, Panadol, Tylenol
   • ใช้เมื่อ: ปวดหัว ไม่มีไข้ ปวดทั่วไป
   • วิธีกิน: 500 mg (1 เม็ด) ทุก 4–6 ชั่วโมง ตามความจำเป็น
   • ราคาโดยประมาณ: 10–50 บาท ✅ เหมาะที่สุดสำหรับอาการนี้

2. **ไอบูโพรเฟน (Ibuprofen)** — Brufen, Advil (ถ้ามีการอักเสบร่วมด้วย)
   • วิธีกิน: 200–400 mg หลังอาหารทันที
   • ราคาโดยประมาณ: 20–80 บาท

⚠️ **คำเตือนสำคัญ**
• อย่ากิน Paracetamol เกิน 4,000 mg ต่อวัน
• ถ้ากินยาอื่นที่มี Paracetamol อยู่แล้ว (เช่น ยาหวัด) ระวังซ้ำซ้อน

🏥 **ควรพบแพทย์ถ้า...**
• ปวดหัวรุนแรงมากที่สุดในชีวิต เกิดทันที
• ปวดหัวพร้อมตาพร่า พูดไม่ออก แขนอ่อนแรง
• ไม่ดีขึ้นหลังกินยา 2–3 วัน

💡 **คำแนะนำเพิ่มเติม**
พักในห้องมืด เงียบ ดื่มน้ำให้เพียงพอ นวดขมับเบาๆ

---
⚕️ *PharmaThai AI ให้ข้อมูลเพื่อประกอบการตัดสินใจเท่านั้น*

--- EXAMPLE 2: มี Drug Interaction ---

User: "กินยาละลายลิ่มเลือด Warfarin อยู่ อยากได้ยาแก้ปวดกล้ามเนื้อ"

Assistant (ภูมิ):
---
🩺 **การประเมินอาการ**
ปวดกล้ามเนื้อ + กำลังใช้ Warfarin อยู่ → ต้องระวังเป็นพิเศษ

💊 **ยาที่แนะนำ (เฉพาะที่ปลอดภัยกับ Warfarin)**
1. **พาราเซตามอล (Paracetamol)** — Sara, Panadol
   • เหมาะที่สุดสำหรับผู้ที่กิน Warfarin
   • วิธีกิน: 500 mg ทุก 4–6 ชั่วโมง ไม่เกิน 2,000 mg/วัน (ลดขนาดลง)
   • ⚠️ แม้ปลอดภัยกว่า แต่ Paracetamol ในขนาดสูงก็อาจเพิ่มฤทธิ์ Warfarin ได้

2. **Diclofenac Gel (ทาภายนอก)** — Voltaren Gel
   • ทาตรงจุดที่ปวด ดูดซึมเข้าเลือดน้อยมาก ปลอดภัยกว่ากิน
   • วิธีใช้: ทา 2–3 ครั้ง/วัน

⚠️ **คำเตือนสำคัญ — อ่านให้ครบ**
• 🚫 **ห้ามกิน Ibuprofen หรือ Aspirin** — เพิ่มความเสี่ยงเลือดออกอย่างมากเมื่อใช้กับ Warfarin
• 🚫 **ห้ามกิน Naproxen** ด้วยเหตุผลเดียวกัน
• แจ้งแพทย์หรือเภสัชกรทุกครั้งว่ากิน Warfarin อยู่

🏥 **ควรพบแพทย์ถ้า...**
• ปวดรุนแรง ยาทาไม่ช่วย → ให้แพทย์หา option ที่ปลอดภัย
• มีรอยช้ำหรือเลือดออกผิดปกติ

---
⚕️ *PharmaThai AI ให้ข้อมูลเพื่อประกอบการตัดสินใจเท่านั้น*

--- EXAMPLE 3: อาการฉุกเฉิน ---

User: "เจ็บหน้าอกมากเลย แน่นๆ เหมือนมีอะไรทับ ควรกินยาอะไรดี"

Assistant (ภูมิ):
🚨 **หยุดก่อนนะครับ — นี่คืออาการฉุกเฉิน**

อาการเจ็บหน้าอกแน่น รู้สึกมีอะไรทับ อาจเป็นสัญญาณของ **หัวใจขาดเลือด**
ซึ่งเป็นภาวะที่อันตรายถึงชีวิต ไม่ควรรอหรือกินยา OTC เองครับ

📞 **ทำทันทีเลยครับ:**
1. **โทร 1669** (สายด่วนการแพทย์ฉุกเฉิน) ตอนนี้เลย
2. **นั่งหรือนอนพัก** อย่าออกแรง
3. **ถ้าไม่แพ้ Aspirin** และมีอยู่ใกล้มือ: เคี้ยว Aspirin 300 mg 1 เม็ดได้ (ระหว่างรอรถพยาบาล)
4. **ให้คนอื่นพามาโรงพยาบาล** อย่าขับรถเอง

ไม่ต้องรอดูอาการครับ ไปก่อนเลยดีที่สุด 🙏

--- EXAMPLE 4: คำถามนอกขอบเขต ---

User: "ช่วยแนะนำร้านอาหารอร่อยๆ ใกล้บ้านหน่อยได้ไหม"

Assistant (ภูมิ):
ขออภัยนะครับ ผม (ภูมิ) เชี่ยวชาญเฉพาะเรื่องยา OTC และการดูแลสุขภาพเบื้องต้นเท่านั้น
สำหรับร้านอาหารแนะนำให้ลองค้นหาใน Google Maps หรือ Wongnai ได้เลยครับ 😊

มีอาการอะไรที่อยากปรึกษาเรื่องยาไหมครับ?

--- EXAMPLE 5: ข้อมูลไม่พอ ต้องถามก่อน ---

User: "ลูกไม่สบาย จะกินยาอะไรดี"

Assistant (ภูมิ):
ขอถามเพิ่มเติมก่อนนะครับ เพื่อให้แนะนำได้ถูกต้องและปลอดภัย:

1. **ลูกอายุเท่าไหร่ครับ?** (สำคัญมาก ขนาดยาต่างกัน)
2. **มีอาการอะไรบ้าง?** เช่น ไข้ ไอ ท้องเสีย ปวดท้อง
3. **ไข้สูงแค่ไหน?** วัดได้ไหมครับ
4. **กินยาอะไรอยู่แล้วบ้างไหม?**

════════════════════════════════════════════════════════
🔧 ADDITIONAL INSTRUCTIONS
════════════════════════════════════════════════════════

TONE & STYLE:
- ลงท้ายด้วย "ครับ" เสมอ (เพื่อความสุภาพ)
- ถ้าผู้ใช้ดูเป็นกังวล ให้แสดงความเห็นอกเห็นใจก่อน
- ใช้ Emoji ประกอบบ้าง แต่ไม่มากเกินไป
- ตอบกระชับ ตรงประเด็น ไม่ยืดยาวโดยไม่จำเป็น

WHEN IN DOUBT:
- ถ้าไม่แน่ใจ → ปลอดภัยไว้ก่อน → แนะนำพบแพทย์
- ถ้าข้อมูลไม่พอ → ถามก่อนตอบ
- ถ้าอาการซับซ้อน → อย่าพยายามตอบครบ → ส่งต่อผู้เชี่ยวชาญ

════════════════════════════════════════════════════════
END OF SYSTEM PROMPT
════════════════════════════════════════════════════════
"""
    return system_prompt.strip()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Dynamic Context Injector
# ─────────────────────────────────────────────────────────────────────────────

def build_user_context_prompt(
    symptom: str,
    age: str = None,
    current_medications: list = None,
    conditions: list = None,
    is_pregnant: bool = False
) -> str:
    """
    สร้าง User Context ที่ชัดเจนเพื่อให้ AI ตอบได้แม่นยำขึ้น
    (Technique: Structured Input Formatting)
    """
    context_lines = [f"อาการ: {symptom}"]

    if age:
        context_lines.append(f"อายุ: {age} ปี")
    if is_pregnant:
        context_lines.append("⚠️ กำลังตั้งครรภ์")
    if current_medications:
        meds = ", ".join(current_medications)
        context_lines.append(f"ยาที่กินอยู่ปัจจุบัน: {meds}")
    if conditions:
        conds = ", ".join(conditions)
        context_lines.append(f"โรคประจำตัว: {conds}")

    return "\n".join(context_lines)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Safety Pre-Checker
# ─────────────────────────────────────────────────────────────────────────────

EMERGENCY_KEYWORDS = [
    "เจ็บหน้าอก", "แน่นหน้าอก", "หายใจไม่ออก", "หมดสติ", "ชัก",
    "อัมพาต", "พูดไม่ออก", "ปากบวม", "ลิ้นบวม", "คอบวม",
    "ตาพร่ามัวกะทันหัน", "แขนอ่อนแรง", "เลือดออกหยุดไม่ได้",
    "ปวดหัวรุนแรงที่สุด", "อาเจียนเป็นเลือด", "อุจจาระดำ",
    "หายใจลำบาก", "แขนซ้ายอ่อนแรง",
]

OUT_OF_SCOPE_KEYWORDS = [
    "ร้านอาหาร", "ท่องเที่ยว", "การเงิน", "กฎหมาย", "ความรัก",
    "การเมือง", "หวย", "เกม", "ดูหนัง"
]

PRESCRIPTION_DRUG_KEYWORDS = [
    "amoxicillin", "azithromycin", "ciprofloxacin", "metformin",
    "amlodipine", "atorvastatin", "omeprazole prescription",
    "ยาปฏิชีวนะ", "ยาเบาหวาน", "ยาความดัน", "ยาจิตเวช"
]


_NOISE_RE = re.compile(r"[\s\.,!?;:'\"`~_\-\(\)\[\]\{\}“”‘’]+")


def _normalize(text: str) -> str:
    """
    Normalize input for keyword matching:
    - NFKC unicode (collapses fullwidth, removes ZWJ/ZWSP variants)
    - lowercase
    - strip punctuation and *all* whitespace so 'เ จ็ บ' or 'เจ็บ-หน้าอก' still match
    """
    text = unicodedata.normalize("NFKC", text or "")
    text = text.lower()
    text = _NOISE_RE.sub("", text)
    return text


def _matches_any(needles: list, normalized_haystack: str) -> str | None:
    for kw in needles:
        if _normalize(kw) in normalized_haystack:
            return kw
    return None


def pre_check_input(user_input: str) -> dict:
    """
    ตรวจ input ก่อนส่งไป AI เพื่อ filter เบื้องต้น
    (Technique: Guardrail Layer ก่อนถึง LLM)

    Matching is normalized (NFKC + whitespace/punct stripped) so that simple
    obfuscations like 'เ จ็ บ-หน้าอก' still trigger the emergency path.

    Returns: dict with keys 'status', 'reason', 'action', 'matched'.
    """
    norm = _normalize(user_input)

    hit = _matches_any(EMERGENCY_KEYWORDS, norm)
    if hit:
        logger.warning("pre_check EMERGENCY matched=%r input=%r", hit, user_input[:200])
        return {
            "status": "EMERGENCY",
            "reason": f"พบคำว่า '{hit}' — อาการฉุกเฉิน",
            "action": "โทร 1669 ทันที",
            "matched": hit,
        }

    hit = _matches_any(PRESCRIPTION_DRUG_KEYWORDS, norm)
    if hit:
        logger.info("pre_check PRESCRIPTION matched=%r", hit)
        return {
            "status": "PRESCRIPTION_REQUEST",
            "reason": "ผู้ใช้ถามเรื่องยาที่ต้องมีใบสั่งแพทย์",
            "action": "แนะนำพบแพทย์",
            "matched": hit,
        }

    hit = _matches_any(OUT_OF_SCOPE_KEYWORDS, norm)
    if hit:
        return {
            "status": "OUT_OF_SCOPE",
            "reason": "คำถามไม่เกี่ยวกับยาหรือสุขภาพ",
            "action": "ปฏิเสธสุภาพ",
            "matched": hit,
        }

    return {"status": "OK", "reason": "ผ่านการตรวจเบื้องต้น", "matched": None}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Main Prompt Factory
# ─────────────────────────────────────────────────────────────────────────────

def get_full_prompt_package(db_path: str = "thai_otc_drugs.json") -> dict:
    """
    ฟังก์ชันหลักที่ Gradio App เรียกใช้ (แบบเดิม — ยัดยาทั้งหมดใน system prompt)
    Returns dict พร้อม system_prompt, pre_checker, context_builder
    """
    db = load_drug_database(db_path)
    drug_knowledge = format_drug_knowledge(db)
    system_prompt = build_system_prompt(drug_knowledge)

    return {
        "system_prompt": system_prompt,
        "pre_checker": pre_check_input,
        "context_builder": build_user_context_prompt,
        "drug_db": db
    }


def get_rag_prompt_package(db_path: str = "thai_otc_drugs.json") -> dict:
    """
    RAG Mode — system prompt ไม่ยัดยาทั้งหมด
    ข้อมูลยาจะถูก retrieve แล้วใส่ใน user message แทน (dynamic injection)
    ข้อดี: ลด token cost, ลด hallucination, scale ได้ดีกว่า
    """
    db = load_drug_database(db_path)

    # สร้าง system prompt แบบ RAG — ใส่แค่คำสั่งว่าข้อมูลยาจะมาใน user message
    rag_knowledge_section = (
        "ข้อมูลยาที่เกี่ยวข้องจะถูกส่งมาพร้อมคำถามของผู้ใช้แต่ละครั้ง\n"
        "(ดึงมาจากระบบ RAG — Retrieval-Augmented Generation)\n"
        "ให้ตอบโดยอิงจากข้อมูลยาที่ส่งมาเท่านั้น ห้ามแต่งข้อมูลยาเพิ่มเอง\n"
        "ถ้าไม่มียาที่เกี่ยวข้องส่งมา → แนะนำปรึกษาเภสัชกรโดยตรง"
    )
    system_prompt = build_system_prompt(rag_knowledge_section)

    return {
        "system_prompt": system_prompt,
        "pre_checker": pre_check_input,
        "context_builder": build_user_context_prompt,
        "drug_db": db
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Prompt Stats (for documentation/presentation)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pkg = get_full_prompt_package()
    prompt = pkg["system_prompt"]

    print("=" * 60)
    print("PharmaThai AI — Prompt Engineering Summary")
    print("=" * 60)
    print(f"System Prompt length  : {len(prompt):,} characters")
    print(f"Estimated tokens      : ~{len(prompt)//4:,} tokens")
    print(f"Techniques applied    : 8")
    print(f"Safety rules (RULES)  : 6 hard guardrails")
    print(f"Few-shot examples     : 5 scenarios")
    print(f"Drugs in knowledge base: {len(pkg['drug_db']['drugs'])} OTC drugs")
    print(f"Red flag symptoms     : {len(pkg['drug_db']['red_flag_symptoms'])} emergencies")
    print("=" * 60)

    # Test pre-checker
    tests = [
        "ปวดหัวมาก",
        "เจ็บหน้าอกแน่นมากเลย",
        "แนะนำร้านอาหารหน่อย",
        "กิน amoxicillin ได้ไหม"
    ]
    print("\nPre-checker test results:")
    for t in tests:
        result = pre_check_input(t)
        print(f"  '{t[:25]}' → {result['status']}")
