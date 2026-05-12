"""
=============================================================================
PharmaThai AI — RAG Engine (Retrieval-Augmented Generation)
CS460 Artificial Intelligence | Technical Execution (Rubric Item 3)
=============================================================================
เทคนิค AI ที่ใช้:
  1. TF-IDF Vectorization  — แปลงข้อมูลยาเป็น vector
  2. Cosine Similarity     — คำนวณความคล้ายอาการ → ยา
  3. Keyword Extraction     — ดึงคำสำคัญจาก input ภาษาไทย
  4. Re-ranking            — เรียงลำดับตาม relevance score
  5. Context Window Mgmt   — ส่งเฉพาะยาที่เกี่ยวข้องให้ LLM

ทำไมใช้ RAG แทน Fine-tuning:
  - ข้อมูลยาเปลี่ยนบ่อย (ราคา, availability) → fine-tune ต้อง retrain
  - RAG อัพเดต JSON แล้วใช้ได้ทันที ไม่มีค่า training
  - ลด hallucination เพราะ LLM เห็นเฉพาะข้อมูลที่ retrieve มา
  - ลด token cost: ส่ง 3-5 ยาแทน 25 ยา
=============================================================================
"""

import json
import math
import re
from collections import Counter

# Punctuation/whitespace splitter — includes Thai/typographic quotes and fullwidth parens.
# Earlier versions used a literal raw-string with curly quotes that silently lost them
# at parse time; we now name the codepoints explicitly.
_PUNCT_SPLIT_RE = re.compile(
    r'[\s,./;:!?()（）\[\]{}'
    r'"“”'   # " " "
    r"'‘’"  # ' ' '
    r'`]+'
)

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Thai Text Tokenizer (Simple word segmentation)
# ─────────────────────────────────────────────────────────────────────────────

# คำที่ไม่มีความหมาย (stop words) สำหรับภาษาไทย
THAI_STOP_WORDS = {
    "มาก", "มี", "ไม่", "ได้", "ที่", "จะ", "ก็", "แล้ว", "อยู่", "เป็น",
    "ใน", "กับ", "ให้", "หรือ", "แต่", "อยาก", "ครับ", "ค่ะ", "คะ", "นะ",
    "เลย", "ด้วย", "ตอน", "วัน", "นี้", "หน่อย", "จัง", "ของ", "ทำ",
    "ถ้า", "และ", "คือ", "มา", "ไป", "อะไร", "ยัง", "เมื่อ", "กิน",
    "ตั้งแต่", "หลัง", "ก่อน", "ดี", "ไหม", "บ้าง", "เอา", "ช่วย",
}


def tokenize_thai(text: str, medical_terms: set = None) -> list:
    """
    Thai tokenizer พร้อม medical term matching:
    1. จับ medical terms ที่รู้จักก่อน (จาก drug database)
    2. แยกด้วย space + punctuation
    3. ตัด stop words
    4. ดึง English words ออกมาด้วย (ชื่อยา)
    """
    text_lower = text.lower().strip()
    tokens = []

    # ── Step 1: Match known medical terms (substring matching) ──
    if medical_terms:
        for term in medical_terms:
            if term in text_lower:
                tokens.append(term)

    # ── Step 2: แยก English words ──
    eng_words = re.findall(r'[a-zA-Z]+', text_lower)
    tokens.extend([w.lower() for w in eng_words])

    # ── Step 3: แยก Thai words ทั่วไป ──
    thai_tokens = _PUNCT_SPLIT_RE.split(text_lower)
    thai_tokens = [t for t in thai_tokens if t and len(t) > 1]
    tokens.extend(thai_tokens)

    # ── Step 4: ตัด stop words + deduplicate ──
    seen = set()
    filtered = []
    for t in tokens:
        if t not in THAI_STOP_WORDS and len(t) > 1 and t not in seen:
            filtered.append(t)
            seen.add(t)

    return filtered


def extract_medical_terms(db: dict) -> set:
    """
    ดึงคำศัพท์ทางการแพทย์ทั้งหมดจาก drug database
    ใช้เป็น dictionary สำหรับ tokenizer
    """
    terms = set()
    for drug in db["drugs"]:
        # ชื่อยา
        terms.add(drug["name_thai"].lower())
        terms.add(drug["name_generic"].lower())
        for brand in drug["common_brands"]:
            terms.add(brand.lower())

        # อาการที่รักษา (สำคัญที่สุด)
        for symptom in drug["symptoms_treated"]:
            terms.add(symptom.lower())

        # ข้อห้าม
        for contra in drug["contraindications"]:
            terms.add(contra.lower())

        # หมวดหมู่
        terms.add(drug["category"].lower())

    # Red flags
    for flag in db["red_flag_symptoms"]:
        terms.add(flag["symptom"].lower())

    # ตัดคำสั้นเกินไป
    terms = {t for t in terms if len(t) > 1}
    return terms


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: TF-IDF Engine
# ─────────────────────────────────────────────────────────────────────────────

class TFIDFEngine:
    """
    TF-IDF Vectorizer สำหรับ Drug Retrieval
    สร้าง document vector จากข้อมูลยา แล้วค้นหาด้วย cosine similarity
    """

    def __init__(self):
        self.documents = []      # list of {"id": ..., "tokens": [...], "drug": {...}}
        self.idf = {}            # term → IDF score
        self.doc_vectors = []    # list of TF-IDF vectors (dict)
        self.medical_terms = set()  # known medical vocabulary

    def build_index(self, db: dict):
        """สร้าง TF-IDF index จาก drug database"""

        # ── Step 0: สร้าง medical terms dictionary จาก DB ──
        self.medical_terms = extract_medical_terms(db)

        # ── Step 1: สร้าง document สำหรับยาแต่ละตัว ──
        self.documents = []
        for drug in db["drugs"]:
            # รวมข้อมูลทั้งหมดของยาเป็น text เดียว
            text_parts = [
                drug["name_thai"],
                drug["name_generic"],
                " ".join(drug["common_brands"]),
                " ".join(drug["symptoms_treated"]),
                " ".join(drug["contraindications"]),
                " ".join(drug["drug_interactions"]),
                " ".join(drug.get("warnings", [])),
                drug["category"],
            ]
            full_text = " ".join(text_parts)
            tokens = tokenize_thai(full_text, self.medical_terms)

            self.documents.append({
                "id": drug["id"],
                "tokens": tokens,
                "drug": drug,
            })

        # ── Step 2: คำนวณ IDF (Inverse Document Frequency) ──
        n_docs = len(self.documents)
        term_doc_count = Counter()

        for doc in self.documents:
            unique_terms = set(doc["tokens"])
            for term in unique_terms:
                term_doc_count[term] += 1

        self.idf = {}
        for term, count in term_doc_count.items():
            # IDF = log(N / df) + 1 (smoothed)
            self.idf[term] = math.log(n_docs / count) + 1

        # ── Step 3: คำนวณ TF-IDF vector สำหรับแต่ละยา ──
        self.doc_vectors = []
        for doc in self.documents:
            tf = Counter(doc["tokens"])
            total = len(doc["tokens"])
            vector = {}
            for term, count in tf.items():
                tf_score = count / total  # normalized TF
                vector[term] = tf_score * self.idf.get(term, 1.0)
            self.doc_vectors.append(vector)

        return len(self.documents)

    def search(self, query: str, top_k: int = 5) -> list:
        """
        ค้นหายาที่เกี่ยวข้องกับ query ด้วย cosine similarity
        Returns: list of {"drug": {...}, "score": float, "matched_terms": [...]}
        """
        # ── Step 1: สร้าง query vector ──
        query_tokens = tokenize_thai(query, self.medical_terms)
        if not query_tokens:
            return []

        query_tf = Counter(query_tokens)
        total = len(query_tokens)
        query_vector = {}
        for term, count in query_tf.items():
            tf_score = count / total
            query_vector[term] = tf_score * self.idf.get(term, 1.0)

        # ── Step 2: คำนวณ cosine similarity กับทุก document ──
        results = []
        for i, doc_vec in enumerate(self.doc_vectors):
            score = self._cosine_similarity(query_vector, doc_vec)
            if score > 0:
                # หา matched terms สำหรับ explainability
                matched = [t for t in query_tokens if t in doc_vec]
                results.append({
                    "drug": self.documents[i]["drug"],
                    "score": round(score, 4),
                    "matched_terms": list(set(matched)),
                })

        # ── Step 3: เรียงตาม score สูงสุด ──
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    @staticmethod
    def _cosine_similarity(vec_a: dict, vec_b: dict) -> float:
        """คำนวณ cosine similarity ระหว่าง 2 sparse vectors"""
        # Dot product
        common_terms = set(vec_a.keys()) & set(vec_b.keys())
        if not common_terms:
            return 0.0

        dot = sum(vec_a[t] * vec_b[t] for t in common_terms)

        # Magnitudes
        mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
        mag_b = math.sqrt(sum(v * v for v in vec_b.values()))

        if mag_a == 0 or mag_b == 0:
            return 0.0

        return dot / (mag_a * mag_b)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Drug Interaction Checker (Rule-based)
# ─────────────────────────────────────────────────────────────────────────────

def check_interactions(recommended_drugs: list, current_medications: list) -> list:
    """
    ตรวจ Drug Interaction ระหว่างยาที่จะแนะนำ กับยาที่ผู้ใช้กินอยู่
    Returns: list of interaction warnings
    """
    if not current_medications:
        return []

    warnings = []
    current_meds_lower = [m.lower().strip() for m in current_medications]

    for drug in recommended_drugs:
        for interaction in drug.get("drug_interactions", []):
            interaction_lower = interaction.lower()
            for med in current_meds_lower:
                if med in interaction_lower or any(
                    part.strip().lower() in interaction_lower
                    for part in med.split()
                ):
                    warnings.append({
                        "drug": drug["name_thai"],
                        "interacts_with": med,
                        "detail": interaction,
                        "severity": "HIGH" if any(
                            w in interaction_lower
                            for w in ["อันตราย", "ห้าม", "เสี่ยง", "เพิ่มฤทธิ์"]
                        ) else "MODERATE",
                    })

    return warnings


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: RAG Pipeline (ตัวหลัก)
# ─────────────────────────────────────────────────────────────────────────────

class PharmathaiRAG:
    """
    RAG Pipeline หลัก:
      Query → Retrieve (TF-IDF) → Check Interactions → Augment Prompt → Generate
    """

    def __init__(self, db_path: str = "thai_otc_drugs.json"):
        # โหลด database
        with open(db_path, "r", encoding="utf-8") as f:
            self.db = json.load(f)

        # สร้าง TF-IDF index
        self.engine = TFIDFEngine()
        n_drugs = self.engine.build_index(self.db)

        print(f"[RAG] Indexed {n_drugs} drugs with TF-IDF")
        print(f"[RAG] Vocabulary size: {len(self.engine.idf)} terms")

    def retrieve_and_augment(
        self,
        user_query: str,
        current_medications: list = None,
        top_k: int = 5,
    ) -> dict:
        """
        RAG Pipeline หลัก:
        1. Retrieve ยาที่เกี่ยวข้อง
        2. Check drug interactions
        3. สร้าง augmented context สำหรับ LLM

        Returns: {
            "retrieved_drugs": [...],
            "interactions": [...],
            "augmented_context": "..." (text สำหรับแทรกใน prompt)
            "retrieval_metadata": {...} (สำหรับ logging/debugging)
        }
        """
        # ── Step 1: Retrieve ──
        results = self.engine.search(user_query, top_k=top_k)
        retrieved_drugs = [r["drug"] for r in results]

        # ── Step 2: Check Interactions ──
        interactions = check_interactions(retrieved_drugs, current_medications or [])

        # ── Step 3: Augment — สร้าง context text ──
        context_lines = []

        if retrieved_drugs:
            context_lines.append("=== ยาที่เกี่ยวข้องกับอาการ (Retrieved by RAG) ===\n")
            for i, res in enumerate(results):
                drug = res["drug"]
                context_lines.append(
                    f"[{drug['id']}] {drug['name_thai']} ({drug['name_generic']})"
                    f"  — relevance: {res['score']:.2f}"
                )
                context_lines.append(f"  แบรนด์: {', '.join(drug['common_brands'])}")
                context_lines.append(f"  ใช้รักษา: {', '.join(drug['symptoms_treated'])}")
                if "dosage" in drug:
                    context_lines.append(f"  ขนาดผู้ใหญ่: {drug['dosage'].get('adult', '-')}")
                    context_lines.append(f"  ขนาดเด็ก: {drug['dosage'].get('child', 'ปรึกษาเภสัชกร')}")
                context_lines.append(
                    f"  ข้อห้าม: "
                    f"{', '.join(drug['contraindications']) if drug['contraindications'] else 'ไม่มีที่สำคัญ'}"
                )
                context_lines.append(
                    f"  ยาที่ระวังเมื่อกินร่วม: "
                    f"{', '.join(drug['drug_interactions']) if drug['drug_interactions'] else 'ไม่มี'}"
                )
                if drug.get("warnings"):
                    context_lines.append(f"  คำเตือน: {' | '.join(drug['warnings'])}")
                context_lines.append(
                    f"  ควรพบแพทย์เมื่อ: {' | '.join(drug['should_see_doctor_if'])}"
                )
                context_lines.append(
                    f"  ราคาประมาณ: {drug.get('price_range_thb', 'ไม่ทราบ')} บาท"
                )
                context_lines.append("")
        else:
            context_lines.append("=== ไม่พบยาที่ตรงกับอาการในฐานข้อมูล ===")
            context_lines.append("แนะนำให้ปรึกษาเภสัชกรหรือแพทย์โดยตรง")

        if interactions:
            context_lines.append("\n⚠️ === Drug Interaction Alert ===")
            for warn in interactions:
                context_lines.append(
                    f"  🚫 {warn['drug']} + {warn['interacts_with']}: "
                    f"{warn['detail']} [{warn['severity']}]"
                )

        # Red flags (ใส่ทุกครั้งเพื่อ safety)
        context_lines.append("\n=== อาการฉุกเฉิน (ห้ามแนะนำยา) ===")
        for flag in self.db["red_flag_symptoms"]:
            context_lines.append(f"  ⚠️ {flag['symptom']} → {flag['action']}")

        augmented_context = "\n".join(context_lines)

        return {
            "retrieved_drugs": retrieved_drugs,
            "interactions": interactions,
            "augmented_context": augmented_context,
            "retrieval_metadata": {
                "query": user_query,
                "n_results": len(results),
                "scores": [r["score"] for r in results],
                "matched_terms": [r["matched_terms"] for r in results],
                "drug_ids": [r["drug"]["id"] for r in results],
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Test / Demo
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    rag = PharmathaiRAG("thai_otc_drugs.json")

    test_queries = [
        ("ปวดหัวมาก ไม่มีไข้", []),
        ("ไอแห้ง ไอตลอดทั้งคืน", []),
        ("ปวดกล้ามเนื้อ กิน Warfarin อยู่", ["Warfarin"]),
        ("ท้องเสีย ถ่ายเหลว", []),
        ("แพ้อากาศ จาม น้ำมูกไหล", []),
        ("คัดจมูก กินยาความดันอยู่", ["ยาความดัน"]),
        ("ผื่นคัน ลมพิษ", []),
        ("กรดไหลย้อน แสบท้อง", []),
    ]

    for query, meds in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        if meds:
            print(f"Current meds: {meds}")

        result = rag.retrieve_and_augment(query, meds, top_k=3)

        print(f"Retrieved {result['retrieval_metadata']['n_results']} drugs:")
        for i, drug in enumerate(result["retrieved_drugs"]):
            score = result["retrieval_metadata"]["scores"][i]
            terms = result["retrieval_metadata"]["matched_terms"][i]
            print(f"  {i+1}. {drug['name_thai']} ({drug['name_generic']}) — score: {score:.3f} | matched: {terms}")

        if result["interactions"]:
            print(f"⚠️  Interactions found: {len(result['interactions'])}")
            for w in result["interactions"]:
                print(f"  🚫 {w['drug']} + {w['interacts_with']}: {w['detail']}")

    print(f"\n{'='*60}")
    print("RAG Engine test complete")
