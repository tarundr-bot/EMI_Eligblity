"""
app.py
------
Chainlit frontend for the Loan Eligibility & EMI Advisor.

Pipeline (per user message):
  1. collect_user_details()   -> LLM extracts fields from chat
  2. merge_new_fields()       -> update session state
  3. show_progress()          -> checklist of collected/missing fields
  4. check_all_fields_ready() -> if all 4 fields collected:
  5. confirm_details()        -> LLM confirms collected data
  6. run_eligibility_engine() -> engine.py computes eligibility
  7. explain_result()         -> LLM explains result in plain language
  8. render_result()          -> nicely formatted Chainlit output + actions
"""

import asyncio
import sniffio

# Monkeypatch sniffio to fix Python 3.14 event loop detection under nest_asyncio
_original_current_async_library = sniffio.current_async_library

def _patched_current_async_library():
    try:
        asyncio.get_running_loop()
        return "asyncio"
    except RuntimeError:
        pass
    return _original_current_async_library()

sniffio.current_async_library = _patched_current_async_library

import chainlit as cl
import os
import shutil

# Ensure public/ directory exists and copy the advisor avatar if it exists
try:
    _src = r""
    _dst_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
    _dst = os.path.join(_dst_dir, "advisor_avatar.png")
    if os.path.exists(_src):
        os.makedirs(_dst_dir, exist_ok=True)
        shutil.copy(_src, _dst)
except Exception as e:
    print(f"Error copying avatar file: {e}")

import configuration
import llm
import engine

# Phrases that mean "start a fresh assessment" instead of ordinary chat
RESET_KEYWORDS = {
    "new assessment", "start over", "reset", "recalculate",
    "new check", "start again", "restart",
}

FIELD_ICONS = {
    "monthly_income": "💰",
    "existing_emi": "📉",
    "down_payment": "🏦",
    "loan_tenure_years": "📅",
}


# ---------------------------------------------------------------------------
# Step 1: Start a new chat session
# ---------------------------------------------------------------------------
@cl.on_chat_start
async def start_session():
    # Register the avatar for Loan Advisor
    try:
        avatar_path = os.path.join("public", "advisor_avatar.png")
        if os.path.exists(avatar_path):
            await cl.Avatar(
                name="Loan Advisor",
                path=avatar_path,
            ).send()
    except Exception as e:
        print(f"Error setting avatar: {e}")
    await begin_new_assessment()


async def begin_new_assessment():
    cl.user_session.set("validated_fields", {})
    cl.user_session.set("assessment_done", False)

    greeting = llm.get_initial_greeting()
    cl.user_session.set("conversation_history", [{"role": "assistant", "content": greeting}])

    await cl.Message(
        content=f"### 🏦 Loan Eligibility Calculator\n\n{greeting}",
        author="Loan Advisor",
    ).send()
    await show_progress({})


# ---------------------------------------------------------------------------
# Step 2: Handle every user message
# ---------------------------------------------------------------------------
@cl.on_message
async def handle_message(message: cl.Message):
    if message.content.strip().lower() in RESET_KEYWORDS:
        await begin_new_assessment()
        return

    validated_fields = cl.user_session.get("validated_fields")
    conversation_history = cl.user_session.get("conversation_history")
    assessment_done = cl.user_session.get("assessment_done")

    if assessment_done:
        await cl.Message(
            content="Your assessment is complete. Click **🔄 New Assessment** below "
                    "to check eligibility with different numbers.",
            author="Loan Advisor",
            actions=[new_assessment_action()],
        ).send()
        return

    conversation_history.append({"role": "user", "content": message.content})

    ai_result = collect_user_details(message.content, validated_fields, conversation_history)

    validated_fields = merge_new_fields(validated_fields, ai_result["extracted_fields"])
    conversation_history.append({"role": "assistant", "content": ai_result["response"]})

    cl.user_session.set("validated_fields", validated_fields)
    cl.user_session.set("conversation_history", conversation_history)

    await cl.Message(content=ai_result["response"], author="Loan Advisor").send()

    if check_all_fields_ready(validated_fields):
        await run_eligibility_pipeline(validated_fields, conversation_history)
        cl.user_session.set("assessment_done", True)
    else:
        await show_progress(validated_fields)


# ---------------------------------------------------------------------------
# Step 3: LLM call to extract fields from the latest message
# ---------------------------------------------------------------------------
def collect_user_details(user_input: str, validated_fields: dict, conversation_history: list) -> dict:
    return llm.process_conversation(
        user_input=user_input,
        validated_fields=validated_fields,
        conversation_history=conversation_history,
    )


# ---------------------------------------------------------------------------
# Step 4: Merge newly extracted fields into session state
# ---------------------------------------------------------------------------
def merge_new_fields(validated_fields: dict, new_fields: dict) -> dict:
    validated_fields.update(new_fields)
    return validated_fields


# ---------------------------------------------------------------------------
# Step 5: Visual checklist of which fields are collected so far
# ---------------------------------------------------------------------------
async def show_progress(validated_fields: dict):
    lines = []
    for field in configuration.REQUIRED_FIELDS:
        icon = FIELD_ICONS.get(field, "•")
        label = configuration.FIELD_LABELS.get(field, field)
        if field in validated_fields:
            value = validated_fields[field]
            display = f"₹{value:,.0f}" if field != "loan_tenure_years" else f"{value} years"
            lines.append(f"- {icon} ✅ **{label}:** {display}")
        else:
            lines.append(f"- {icon} ⬜ **{label}:** _pending_")

    await cl.Message(content="**Progress:**\n" + "\n".join(lines), author="Loan Advisor").send()


# ---------------------------------------------------------------------------
# Step 6: Check if all required fields have been collected
# ---------------------------------------------------------------------------
def check_all_fields_ready(validated_fields: dict) -> bool:
    return all(field in validated_fields for field in configuration.REQUIRED_FIELDS)


# ---------------------------------------------------------------------------
# Step 7: Confirm -> run engine -> explain -> render
# ---------------------------------------------------------------------------
async def run_eligibility_pipeline(validated_fields: dict, conversation_history: list):
    confirm_text = llm.ask_answer_confirm(validated_fields)
    await cl.Message(content=confirm_text, author="Loan Advisor").send()

    result = engine.compute_eligibility(validated_fields)

    if "error" in result:
        await cl.Message(
            content="⚠️ Sorry, the eligibility engine is unavailable right now. "
                    "Your details are saved — please try again shortly.",
            author="Loan Advisor",
        ).send()
        return

    explanation = llm.ask_answer_explain(result)
    await cl.Message(content=explanation, author="Loan Advisor").send()

    await render_result(result)

    conversation_history.append({"role": "assistant", "content": explanation})
    cl.user_session.set("conversation_history", conversation_history)


# ---------------------------------------------------------------------------
# Step 8: Render eligibility summary + property matches as a clean UI card
# ---------------------------------------------------------------------------
async def render_result(result: dict):
    status = result.get("status", "Unknown")
    status_icon = "✅" if status == "Eligible" else "⚠️"

    summary = (
        f"### {status_icon} Status: **{status}**\n\n"
        f"| Metric | Value |\n"
        f"|---|---|\n"
        f"| 💳 Eligible EMI | ₹{result.get('eligible_emi', 0):,.0f} |\n"
        f"| 🏗️ Loan Amount | ₹{result.get('loan_amount', 0):,.0f} |\n"
        f"| 🏠 Property Budget | ₹{result.get('property_budget', 0):,.0f} |\n"
    )
    await cl.Message(content=summary, author="Loan Advisor").send()

    properties = result.get("matching_properties", [])
    if not properties:
        await cl.Message(
            content="No properties currently match this budget.",
            author="Loan Advisor",
            actions=[new_assessment_action()],
        ).send()
        return

    rows = "\n".join(
        f"| {p['id']} | {p['name']} | {p['location']} | ₹{p['price']:,.0f} |"
        for p in properties
    )
    property_table = (
        f"### 🏠 Matching Properties ({len(properties)})\n\n"
        f"| ID | Name | Location | Price |\n"
        f"|---|---|---|---|\n"
        f"{rows}"
    )
    await cl.Message(
        content=property_table,
        author="Loan Advisor",
        actions=[new_assessment_action()],
    ).send()


# ---------------------------------------------------------------------------
# Action button: lets the user start a new assessment with one click
# ---------------------------------------------------------------------------
def new_assessment_action() -> cl.Action:
    return cl.Action(
        name="new_assessment",
        payload={"action": "new_assessment"},
        label="🔄 New Assessment",
    )


@cl.action_callback("new_assessment")
async def on_new_assessment(action: cl.Action):
    await begin_new_assessment()