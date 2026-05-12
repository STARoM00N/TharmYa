"""
Tests for prompt_engine.pre_check_input — focuses on bypass-resistance
since this is the local safety guardrail before the LLM ever sees input.
"""

import logging
import pytest

from prompt_engine import pre_check_input

logging.disable(logging.CRITICAL)


@pytest.mark.parametrize(
    "text",
    [
        "เจ็บหน้าอก",
        "เจ็บหน้าอกมาก แน่นๆ",
        "เ จ็ บ ห น้ า อ ก",          # spaced obfuscation
        "เจ็บ-หน้า-อก",                # punctuation glue
        "เจ็บหน้าอก!!!",
        "ปากบวม ลิ้นบวม",
        "อาเจียนเป็นเลือด",
        "แขนซ้ายอ่อนแรง พูดไม่ออก",
        "ปวดหัวรุนแรงที่สุดในชีวิต",
    ],
)
def test_emergency_triggers(text):
    result = pre_check_input(text)
    assert result["status"] == "EMERGENCY", f"missed: {text!r}"
    assert result["matched"], "should report which keyword matched"


@pytest.mark.parametrize(
    "text",
    [
        "อยากกิน Amoxicillin",
        "AMOXICILLIN",                   # case
        "amoxi cillin",                  # spaced
        "ขอ azithromycin หน่อย",
        "ยาปฏิชีวนะ",
        "ยาเบาหวาน",
    ],
)
def test_prescription_triggers(text):
    result = pre_check_input(text)
    assert result["status"] == "PRESCRIPTION_REQUEST", f"missed: {text!r}"


@pytest.mark.parametrize(
    "text",
    [
        "แนะนำร้านอาหารหน่อย",
        "ดูหนังเรื่องอะไรดี",
        "เล่นเกมอะไรดี",
    ],
)
def test_out_of_scope(text):
    result = pre_check_input(text)
    assert result["status"] == "OUT_OF_SCOPE"


@pytest.mark.parametrize(
    "text",
    [
        "ปวดหัวมาก ไม่มีไข้",
        "ไอแห้ง 3 วันแล้ว",
        "ท้องเสีย ถ่ายเหลว",
        "ผื่นคันตามตัว",
    ],
)
def test_normal_passes(text):
    result = pre_check_input(text)
    assert result["status"] == "OK"


def test_empty_input_is_ok():
    assert pre_check_input("")["status"] == "OK"


def test_emergency_takes_precedence_over_prescription():
    # If a user mentions both, emergency must win
    text = "เจ็บหน้าอก กินยาเบาหวานอยู่"
    assert pre_check_input(text)["status"] == "EMERGENCY"
