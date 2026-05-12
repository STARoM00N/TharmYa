"""
Tests for the RAG engine — tokenizer correctness, retrieval relevance,
and drug-interaction detection.
"""

import os
import pytest

from rag_engine import (
    PharmathaiRAG,
    TFIDFEngine,
    _PUNCT_SPLIT_RE,
    check_interactions,
    extract_medical_terms,
    tokenize_thai,
)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "thai_otc_drugs.json")


@pytest.fixture(scope="module")
def rag():
    return PharmathaiRAG(DB_PATH)


# ─── Tokenizer ─────────────────────────────────────────────────────────────────

class TestTokenizer:
    def test_typographic_quotes_are_split(self):
        # Regression: earlier regex silently lost typographic quotes
        out = _PUNCT_SPLIT_RE.split("ปวด“มาก”หัว")
        assert "ปวด" in out and "มาก" in out and "หัว" in out

    def test_drops_thai_stop_words(self):
        tokens = tokenize_thai("ปวดหัวมาก ไม่มีไข้")
        assert "มาก" not in tokens  # stop word
        assert "ปวดหัว" in " ".join(tokens) or "ปวด" in tokens

    def test_extracts_english_drug_names(self):
        tokens = tokenize_thai("กินยา Paracetamol 500mg")
        assert "paracetamol" in tokens

    def test_medical_term_priority(self):
        terms = {"พาราเซตามอล", "ปวดหัว"}
        tokens = tokenize_thai("ปวดหัวกินพาราเซตามอลได้ไหม", medical_terms=terms)
        assert "ปวดหัว" in tokens
        assert "พาราเซตามอล" in tokens


# ─── Retrieval ────────────────────────────────────────────────────────────────

class TestRetrieval:
    @pytest.mark.parametrize(
        "query, expected_substring",
        [
            ("ปวดหัวมาก ไม่มีไข้", "paracetamol"),
            ("ไอแห้งมาก ไอตลอด", "dextromethorphan"),
            ("ผื่นคัน ลมพิษ", "cetirizine"),
            ("ท้องเสีย ถ่ายเหลว", "loperamide"),
            ("ตาแห้ง แสบตา", "tears"),
        ],
    )
    def test_top_result_is_relevant(self, rag, query, expected_substring):
        result = rag.retrieve_and_augment(query, top_k=3)
        retrieved_names = " ".join(
            d["name_generic"].lower() for d in result["retrieved_drugs"]
        )
        assert expected_substring in retrieved_names, (
            f"query={query!r} retrieved={retrieved_names!r}"
        )

    def test_empty_query_returns_empty(self, rag):
        result = rag.retrieve_and_augment("", top_k=3)
        assert result["retrieved_drugs"] == []

    def test_top_k_respected(self, rag):
        result = rag.retrieve_and_augment("ปวดหัว", top_k=2)
        assert len(result["retrieved_drugs"]) <= 2


# ─── Drug interactions ────────────────────────────────────────────────────────

class TestInteractions:
    def test_no_interactions_when_no_current_meds(self, rag):
        result = rag.retrieve_and_augment("ปวดหัวมาก", current_medications=[], top_k=3)
        assert result["interactions"] == []

    def test_warfarin_interaction_detected(self, rag):
        result = rag.retrieve_and_augment(
            "ปวดหัวมาก",
            current_medications=["Warfarin"],
            top_k=5,
        )
        assert len(result["interactions"]) > 0, "Should flag NSAID/Warfarin clash"
        details = " ".join(w["detail"].lower() for w in result["interactions"])
        assert "warfarin" in details

    def test_severity_classification(self, rag):
        result = rag.retrieve_and_augment(
            "ปวดหัวมาก",
            current_medications=["Warfarin"],
            top_k=5,
        )
        severities = {w["severity"] for w in result["interactions"]}
        assert severities <= {"HIGH", "MODERATE"}


# ─── extract_medical_terms ────────────────────────────────────────────────────

def test_medical_terms_extracted_from_db(rag):
    terms = extract_medical_terms(rag.db)
    # Sanity: should contain common drug names + at least one symptom
    assert any("paracetamol" in t for t in terms)
    assert all(len(t) > 1 for t in terms)
