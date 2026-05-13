"""
=============================================================================
PharmaThai AI — Gradio Web Application
CS460 Artificial Intelligence | Final Project
=============================================================================
รองรับทั้ง Google Gemini และ OpenAI GPT — เลือกผ่าน Environment Variable

วิธีใช้ Gemini:
  export AI_PROVIDER=gemini
  export GEMINI_API_KEY='your-key'
  python3 app.py

วิธีใช้ OpenAI:
  export AI_PROVIDER=openai
  export OPENAI_API_KEY='your-key'
  python3 app.py
=============================================================================
"""

import gradio as gr
import logging
import os
from typing import Iterator
from prompt_engine import (
    get_rag_prompt_package,
    pre_check_input,
    build_user_context_prompt,
)
from rag_engine import PharmathaiRAG

logging.basicConfig(
    level=os.environ.get("PHARMATHAI_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("pharmathai.app")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG: Auto-detect provider จาก env var
# ─────────────────────────────────────────────────────────────────────────────

AI_PROVIDER = os.environ.get("AI_PROVIDER", "").lower()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

# Auto-detect: ถ้าไม่ได้ set AI_PROVIDER ให้ดูว่ามี key ตัวไหน
if not AI_PROVIDER:
    if GEMINI_KEY:
        AI_PROVIDER = "gemini"
    elif OPENAI_KEY:
        AI_PROVIDER = "openai"
    else:
        AI_PROVIDER = "gemini"  # default

# Model names — เปลี่ยนได้ตรงนี้
GEMINI_MODEL = "gemini-2.5-flash"       # หรือ gemini-1.5-pro, gemini-2.0-flash-lite
OPENAI_MODEL = "gpt-4o-mini"            # หรือ gpt-4o, gpt-4.1-mini, gpt-4.1-nano

# ─────────────────────────────────────────────────────────────────────────────
# INIT: Load knowledge base + system prompt + RAG engine
# ─────────────────────────────────────────────────────────────────────────────

pkg = get_rag_prompt_package("thai_otc_drugs.json")
SYSTEM_PROMPT = pkg["system_prompt"]

# Initialize RAG engine (TF-IDF index สำหรับ drug retrieval)
rag = PharmathaiRAG("thai_otc_drugs.json")

# ─────────────────────────────────────────────────────────────────────────────
# LLM WRAPPER: ส่ง message ไปยัง AI provider ที่เลือก
# ─────────────────────────────────────────────────────────────────────────────

def _to_text(content) -> str:
    """
    Normalize a Gradio chat message payload to a plain string.
    Gradio 6.x passes message content as either a string or a list of
    parts like [{"type": "text", "text": "..."}]; older versions pass strings.
    """
    if isinstance(content, list):
        parts = []
        for m in content:
            if isinstance(m, dict) and "text" in m:
                parts.append(m["text"])
            elif isinstance(m, str):
                parts.append(m)
        return " ".join(parts).strip()
    return str(content or "").strip()


def stream_llm(user_message: str, history: list) -> Iterator[str]:
    """
    Yields cumulative response text as the LLM produces it.
    Each yielded value is the *full* response so far (Gradio chatbot expects
    cumulative text, not deltas).
    """
    if AI_PROVIDER == "openai":
        yield from _stream_openai(user_message, history)
    else:
        yield from _stream_gemini(user_message, history)


def _stream_gemini(user_message: str, history: list) -> Iterator[str]:
    import google.generativeai as genai

    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT,
        generation_config=genai.GenerationConfig(
            temperature=0.3,
            top_p=0.8,
            max_output_tokens=2048,
        ),
    )

    gemini_history = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        text = _to_text(msg["content"])
        if text:
            gemini_history.append({"role": role, "parts": [text]})

    chat = model.start_chat(history=gemini_history)
    response = chat.send_message(user_message, stream=True)

    accumulated = ""
    for chunk in response:
        # google-generativeai yields chunks with .text; guard against empty
        piece = getattr(chunk, "text", "") or ""
        if piece:
            accumulated += piece
            yield accumulated
    if not accumulated:
        # Some safety filters return empty stream; fall back to non-streaming
        yield response.text if hasattr(response, "text") else ""


def _normalize_openai_base_url(url: str) -> str:
    """Strip trailing slash + auto-append /v1 for known providers (avoids 404s)."""
    url = url.rstrip("/")
    if any(p in url for p in ("openrouter.ai/api", "api.groq.com/openai", "api.cerebras.ai")) and not url.endswith("/v1"):
        url = url + "/v1"
    return url


def _stream_openai(user_message: str, history: list) -> Iterator[str]:
    from openai import OpenAI

    # OPENAI_BASE_URL lets you point at any OpenAI-compatible host
    # (Groq, OpenRouter, Cerebras, local Ollama, etc.)
    base_url = os.environ.get("OPENAI_BASE_URL")
    if base_url:
        base_url = _normalize_openai_base_url(base_url)
    client = OpenAI(api_key=OPENAI_KEY, base_url=base_url) if base_url else OpenAI(api_key=OPENAI_KEY)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        text = _to_text(msg["content"])
        if text:
            messages.append({"role": msg["role"], "content": text})
    messages.append({"role": "user", "content": user_message})

    stream = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=2048,
        stream=True,
    )

    accumulated = ""
    for event in stream:
        delta = event.choices[0].delta.content if event.choices else None
        if delta:
            accumulated += delta
            yield accumulated


# ─────────────────────────────────────────────────────────────────────────────
# CORE: Chat function
# ─────────────────────────────────────────────────────────────────────────────

def _format_rag_panel(rag_result: dict) -> str:
    """Render RAG retrieval as Markdown for the side panel."""
    drugs = rag_result.get("retrieved_drugs", [])
    meta = rag_result.get("retrieval_metadata", {})
    interactions = rag_result.get("interactions", [])

    if not drugs:
        return "_ไม่พบยาที่ตรงกับอาการในฐานข้อมูล RAG_"

    lines = ["### 🔎 ยาที่ระบบดึงมาให้ AI พิจารณา"]
    for drug, score, terms in zip(
        drugs,
        meta.get("scores", []),
        meta.get("matched_terms", []),
    ):
        lines.append(
            f"- **{drug['name_thai']}** ({drug['name_generic']}) — "
            f"score `{score:.2f}`"
        )
        if terms:
            lines.append(f"  - matched: {', '.join(terms)}")

    if interactions:
        lines.append("\n### ⚠️ Drug Interaction Alert")
        for warn in interactions:
            lines.append(
                f"- 🚫 **{warn['drug']}** + {warn['interacts_with']}: "
                f"{warn['detail']} _[{warn['severity']}]_"
            )
    return "\n".join(lines)


def _short_circuit(history: list, user_message: str, reply: str):
    history = list(history)
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": reply})
    return history


def pharmathai_chat(
    user_message: str,
    history: list,
    age: str,
    current_meds: str,
    conditions: str,
    is_pregnant: bool,
):
    """
    Generator that yields (chatbot_history, input_textbox, rag_panel_md).
    Flow: Pre-check → RAG retrieve → Stream LLM → Update history.
    """

    user_message = _to_text(user_message)
    if not user_message:
        yield history, "", gr.update()
        return

    # ── STEP 1: Safety Pre-check ──
    check = pre_check_input(user_message)

    if check["status"] == "EMERGENCY":
        log.warning("emergency triggered: matched=%r", check.get("matched"))
        reply = (
            "🚨 **หยุดก่อนนะครับ — นี่คืออาการฉุกเฉิน**\n\n"
            f"ระบบตรวจพบ: {check['reason']}\n\n"
            "📞 **โทร 1669** (สายด่วนการแพทย์ฉุกเฉิน) ตอนนี้เลยครับ\n"
            "อย่ารอดูอาการ อย่ากินยาเอง ไปโรงพยาบาลทันที 🙏"
        )
        yield _short_circuit(history, user_message, reply), "", "_ไม่ดึงยา — เป็นอาการฉุกเฉิน_"
        return

    if check["status"] == "OUT_OF_SCOPE":
        reply = (
            "ขออภัยนะครับ ผม (ภูมิ) ช่วยได้เฉพาะเรื่องยา OTC "
            "และสุขภาพเบื้องต้นเท่านั้นครับ\n\n"
            "มีอาการอะไรที่อยากปรึกษาเรื่องยาไหมครับ? 🙏"
        )
        yield _short_circuit(history, user_message, reply), "", "_ไม่ดึงยา — คำถามนอกขอบเขต_"
        return

    if check["status"] == "PRESCRIPTION_REQUEST":
        reply = (
            "ขออภัยครับ ยาที่ถามเป็น **ยาที่ต้องสั่งโดยแพทย์** "
            "ไม่สามารถซื้อเองได้ครับ\n\n"
            "🏥 กรุณาพบแพทย์เพื่อรับใบสั่งยาที่เหมาะสมนะครับ 🙏"
        )
        yield _short_circuit(history, user_message, reply), "", "_ไม่ดึงยา — ยาต้องสั่งโดยแพทย์_"
        return

    # ── STEP 2: Build enriched context ──
    meds_list = [m.strip() for m in current_meds.split(",") if m.strip()] if current_meds else None
    conds_list = [c.strip() for c in conditions.split(",") if c.strip()] if conditions else None

    context = build_user_context_prompt(
        symptom=user_message,
        age=age if age else None,
        current_medications=meds_list,
        conditions=conds_list,
        is_pregnant=is_pregnant,
    )

    rag_result = rag.retrieve_and_augment(
        user_query=user_message,
        current_medications=meds_list,
        top_k=5,
    )
    rag_panel_md = _format_rag_panel(rag_result)

    enriched_message = (
        f"[ข้อมูลผู้ใช้]\n{context}\n\n"
        f"[ข้อมูลยาที่เกี่ยวข้อง — จากระบบ RAG]\n{rag_result['augmented_context']}\n\n"
        f"[คำถาม]\n{user_message}"
    )

    # ── STEP 3: Stream LLM ──
    streaming_history = list(history)
    streaming_history.append({"role": "user", "content": user_message})
    streaming_history.append({"role": "assistant", "content": ""})

    # Show retrieval immediately, even before tokens arrive
    yield streaming_history, "", rag_panel_md

    try:
        for partial in stream_llm(enriched_message, history):
            streaming_history[-1] = {"role": "assistant", "content": partial}
            yield streaming_history, "", rag_panel_md
    except Exception as e:
        log.exception("LLM call failed")
        streaming_history[-1] = {
            "role": "assistant",
            "content": (
                f"⚠️ เกิดข้อผิดพลาดในการเชื่อมต่อ AI: {e}\n\n"
                "กรุณาลองใหม่อีกครั้ง หรือตรวจสอบว่า API Key ถูกต้อง"
            ),
        }
        yield streaming_history, "", rag_panel_md

# ─────────────────────────────────────────────────────────────────────────────
# UI: Gradio Interface
# ─────────────────────────────────────────────────────────────────────────────

CUSTOM_CSS = """
/* ── Base typography: increase everything for elder readability ── */
.gradio-container, .gradio-container * {
    font-size: 18px !important;
    line-height: 1.7 !important;
}
.gradio-container {
    max-width: 1280px !important;
    margin: 0 auto !important;
}

/* ── Header ── */
.pharmathai-header {
    text-align: center;
    padding: 32px 24px;
    background: linear-gradient(135deg, #0d9488, #059669);
    border-radius: 16px;
    margin-bottom: 20px;
    color: white;
    box-shadow: 0 4px 14px rgba(13, 148, 136, 0.25);
}
.pharmathai-header h1 {
    margin: 0;
    font-size: 42px !important;
    font-weight: 800;
    letter-spacing: 0.5px;
}
.pharmathai-header p {
    margin: 10px 0 0;
    opacity: 0.95;
    font-size: 22px !important;
}

/* ── How-to-use panel ── */
.how-to-use {
    background: #ecfdf5;
    border: 2px solid #10b981;
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 18px;
    color: #064e3b;
}
.how-to-use h3 {
    margin: 0 0 12px;
    font-size: 24px !important;
    color: #047857;
}
.how-to-use ol {
    margin: 0;
    padding-left: 28px;
    font-size: 19px !important;
}
.how-to-use li { margin: 6px 0; }

/* ── Section title ── */
.section-title {
    font-size: 24px !important;
    font-weight: 700;
    color: #134e4a;
    margin: 6px 0 10px;
}

/* ── Chatbot bubbles bigger ── */
.gradio-container .message, .gradio-container .message * {
    font-size: 19px !important;
    line-height: 1.75 !important;
}

/* ── Inputs: bigger text and padding ── */
.gradio-container textarea,
.gradio-container input[type="text"],
.gradio-container input[type="number"] {
    font-size: 20px !important;
    padding: 14px 16px !important;
    line-height: 1.5 !important;
}
.gradio-container label,
.gradio-container .label-wrap span {
    font-size: 19px !important;
    font-weight: 600 !important;
    color: #1f2937 !important;
}

/* ── Buttons: large, high-contrast, easy targets ── */
.gradio-container button {
    font-size: 20px !important;
    padding: 14px 22px !important;
    min-height: 56px !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
}
.gradio-container button.primary {
    background: #059669 !important;
    color: white !important;
    box-shadow: 0 3px 8px rgba(5, 150, 105, 0.3);
}
.gradio-container button.primary:hover {
    background: #047857 !important;
    transform: translateY(-1px);
}

/* ── Quick-symptom buttons ── */
.quick-symptoms button {
    background: #f0fdfa !important;
    color: #134e4a !important;
    border: 2px solid #0d9488 !important;
    font-size: 18px !important;
    min-height: 52px !important;
}
.quick-symptoms button:hover {
    background: #ccfbf1 !important;
}

/* ── Disclaimer prominent ── */
.disclaimer {
    background: #fef3c7;
    border-left: 6px solid #f59e0b;
    padding: 16px 20px;
    border-radius: 10px;
    font-size: 17px !important;
    line-height: 1.7 !important;
    color: #78350f;
    margin-top: 14px;
}
.disclaimer b { color: #92400e; font-size: 19px; }

/* ── Checkbox bigger ── */
.gradio-container input[type="checkbox"] {
    width: 22px !important;
    height: 22px !important;
    margin-right: 8px !important;
}

/* ── Accordion title bigger ── */
.gradio-container .label-wrap button {
    font-size: 19px !important;
}
"""

with gr.Blocks(
    title="PharmaThai AI — ถามก่อนซื้อ ปลอดภัยกว่า",
    theme=gr.themes.Soft(
        primary_hue="emerald",
        secondary_hue="teal",
        font=[gr.themes.GoogleFont("Sarabun"), "ui-sans-serif", "system-ui"],
    ),
) as app:

    # ── Header ──
    gr.HTML("""
    <div class="pharmathai-header">
        <h1>💊 PharmaThai AI</h1>
        <p>ถามก่อนซื้อยา ปลอดภัยกว่า — ผู้ช่วยแนะนำยาสามัญสำหรับคนไทย</p>
    </div>
    """)

    # ── How to use (simple steps) ──
    gr.HTML("""
    <div class="how-to-use">
        <h3>📋 วิธีใช้งานง่าย ๆ 3 ขั้นตอน</h3>
        <ol>
            <li><b>พิมพ์อาการ</b> ที่กำลังเป็นอยู่ ลงในช่องด้านล่าง (เช่น "ปวดหัว" หรือ "ไอ")</li>
            <li><b>กดปุ่มสีเขียว "ส่งคำถาม"</b> ทางขวามือ</li>
            <li><b>รอสักครู่</b> ภูมิจะแนะนำยาที่เหมาะสมให้ครับ</li>
        </ol>
    </div>
    """)

    with gr.Row():
        # ── Left: Chat ──
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(
                label="💬 สนทนากับภูมิ — ผู้ช่วยเภสัชกร",
                height=560,
                avatar_images=(None, "💊"),
                show_copy_button=True,
            )

            gr.HTML('<div class="section-title">✍️ พิมพ์อาการของคุณที่นี่</div>')
            with gr.Row():
                user_input = gr.Textbox(
                    placeholder="ตัวอย่าง: ปวดหัวมาก ไม่มีไข้",
                    label="",
                    scale=5,
                    container=False,
                    lines=2,
                )
                send_btn = gr.Button("ส่งคำถาม ➤", variant="primary", scale=1, size="lg")

            # Quick-pick common symptoms (one-tap for elders)
            gr.HTML('<div class="section-title" style="margin-top:14px;">👇 หรือกดเลือกอาการที่พบบ่อย</div>')
            with gr.Row(elem_classes="quick-symptoms"):
                quick_headache = gr.Button("🤕 ปวดหัว")
                quick_fever = gr.Button("🌡️ เป็นไข้")
                quick_cough = gr.Button("😷 ไอ เจ็บคอ")
                quick_stomach = gr.Button("🤢 ปวดท้อง")
                quick_cold = gr.Button("🤧 เป็นหวัด")

            with gr.Accordion("🔬 ดูยาที่ระบบค้นมาให้ AI (สำหรับผู้สนใจรายละเอียด)", open=False):
                rag_panel = gr.Markdown(
                    "_ยังไม่มีคำถาม — ระบบจะแสดงผลการค้นหาที่นี่เมื่อคุณส่งอาการมา_"
                )

        # ── Right: Patient Profile ──
        with gr.Column(scale=1):
            gr.HTML('<div class="section-title">👤 ข้อมูลของคุณ (ถ้ามี จะแม่นยำขึ้น)</div>')
            age_input = gr.Textbox(
                label="อายุ (ปี)",
                placeholder="เช่น 65",
                info="ใส่ตัวเลขอายุของคุณ",
            )
            meds_input = gr.Textbox(
                label="ยาที่กินอยู่ตอนนี้",
                placeholder="เช่น Warfarin, Metformin",
                info="ถ้ามีหลายตัว ให้คั่นด้วยลูกน้ำ ( , )",
                lines=2,
            )
            conditions_input = gr.Textbox(
                label="โรคประจำตัว",
                placeholder="เช่น เบาหวาน, ความดันสูง",
                info="ถ้ามีหลายโรค ให้คั่นด้วยลูกน้ำ ( , )",
                lines=2,
            )
            pregnant_input = gr.Checkbox(
                label="กำลังตั้งครรภ์",
                value=False,
                info="ติ๊กถ้ากำลังตั้งครรภ์",
            )

            gr.HTML("""
            <div class="disclaimer">
                ⚕️ <b>ข้อควรทราบ</b><br>
                PharmaThai AI เป็นเพียง<b>ข้อมูลประกอบ</b>เท่านั้น<br>
                <b>ไม่ใช่การวินิจฉัยจากแพทย์</b><br>
                หากอาการรุนแรงหรือไม่ดีขึ้น<br>
                กรุณา<b>ปรึกษาเภสัชกรหรือแพทย์</b>ทุกครั้ง<br>
                <br>
                🚨 เหตุฉุกเฉิน <b>โทร 1669</b>
            </div>
            """)

            clear_btn = gr.Button("🗑️ ล้างและเริ่มใหม่", variant="secondary", size="lg")

    # ── Event handlers ──
    chat_inputs = [user_input, chatbot, age_input, meds_input, conditions_input, pregnant_input]
    chat_outputs = [chatbot, user_input, rag_panel]

    send_btn.click(fn=pharmathai_chat, inputs=chat_inputs, outputs=chat_outputs)
    user_input.submit(fn=pharmathai_chat, inputs=chat_inputs, outputs=chat_outputs)

    # Quick-symptom buttons: pre-fill the textbox so elders can edit before sending
    quick_headache.click(fn=lambda: "ปวดหัว", outputs=user_input)
    quick_fever.click(fn=lambda: "เป็นไข้ ตัวร้อน", outputs=user_input)
    quick_cough.click(fn=lambda: "ไอ เจ็บคอ", outputs=user_input)
    quick_stomach.click(fn=lambda: "ปวดท้อง", outputs=user_input)
    quick_cold.click(fn=lambda: "เป็นหวัด คัดจมูก น้ำมูกไหล", outputs=user_input)

    clear_btn.click(
        fn=lambda: ([], "", "_ยังไม่มีคำถาม — ระบบจะแสดงผลการค้นหาที่นี่เมื่อคุณส่งอาการมา_"),
        outputs=[chatbot, user_input, rag_panel],
    )


# ─────────────────────────────────────────────────────────────────────────────
# LAUNCH
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    provider_display = AI_PROVIDER.upper()
    model_display = OPENAI_MODEL if AI_PROVIDER == "openai" else GEMINI_MODEL
    key_set = bool(OPENAI_KEY) if AI_PROVIDER == "openai" else bool(GEMINI_KEY)

    print("=" * 50)
    print("PharmaThai AI — Starting Gradio Web App")
    print(f"AI Provider : {provider_display}")
    print(f"Model       : {model_display}")
    print(f"API Key     : {'✅ Set' if key_set else '❌ NOT SET'}")
    print(f"Drugs loaded: {len(pkg['drug_db']['drugs'])}")
    print(f"RAG Engine  : TF-IDF ({len(rag.engine.idf)} terms indexed)")
    print(f"Mode        : RAG (Retrieval-Augmented Generation)")
    print("=" * 50)

    if not key_set:
        if AI_PROVIDER == "openai":
            print("❌ Run: export OPENAI_API_KEY='your-key'")
        else:
            print("❌ Run: export GEMINI_API_KEY='your-key'")

    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,       # เปลี่ยนเป็น True ถ้าจะ demo online
        css=CUSTOM_CSS,
    )
