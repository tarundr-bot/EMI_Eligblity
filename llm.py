import openai
import os
import re
import json
import configuration
import loan_eligiblity_calculator_prompts


def get_client():
    return openai.OpenAI(api_key=configuration.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY"))


# ---------------------------------------------------------------------------
# Python-side normalizer: safety net if the LLM returns raw strings like
# "30k", "1 lakh", "5 years", "60 months" instead of clean numbers.
# Tenure is ALWAYS returned in years (int when whole).
# ---------------------------------------------------------------------------
def normalize_value(field, raw):
    """Convert '30k' / '1 lakh' / '5 years' / '60 months' into a clean number."""
    if isinstance(raw, bool):
        return None

    is_months = False
    is_years_explicit = False
    
    if isinstance(raw, (int, float)):
        num = float(raw)
    else:
        s = str(raw).lower().strip()
        
        # Reject negatives explicitly
        if s.startswith('-') or s.startswith('−'):
            return None
        
        # Check for keywords BEFORE stripping them (critical for tenure validation)
        is_months = "month" in s
        is_years_explicit = "year" in s or "yr" in s
        
        s = s.replace(",", "").replace("₹", "").replace("rs.", "").replace("rs", "")
        mult = 1
        if "crore" in s:
            mult = 10000000
        elif "lakh" in s:
            mult = 100000
        elif "k" in s:
            mult = 1000
        
        # Keywords already captured above, now safe to strip them
        for word in ["crore", "lakh", "k", "years", "year", "yrs", "yr", "months", "month"]:
            s = s.replace(word, "")
        
        m = re.search(r"\d+\.?\d*", s)
        if not m:
            return None
        num = float(m.group()) * mult

    # Field-specific validation and normalization
    if field == "monthly_income" and num >= 1000:
        return int(num) if num == int(num) else num

    if field == "existing_emi" and num >= 0:
        return int(num) if num == int(num) else num

    if field == "down_payment" and num >= 0:
        return int(num) if num == int(num) else num

    if field == "loan_tenure_years":
        # "60 months" or bare number > 30 WITHOUT "year" keyword -> assume months
        if is_months or (num > 30 and not is_years_explicit):
            num = num / 12.0
        # Reject if out of valid range (1-30 years)
        if 1 <= num <= 30:
            return int(num) if num == int(num) else round(num, 2)
        return None

    return None


# ---------------------------------------------------------------------------
# Main conversational call: one LLM call per user message.
# Returns {"response": str, "extracted_fields": dict, "all_fields_collected": bool}
# ---------------------------------------------------------------------------
def process_conversation(user_input, validated_fields, conversation_history):
    client = get_client()

    required = configuration.REQUIRED_FIELDS
    missing = [f for f in required if f not in validated_fields]

    messages = [
        {"role": "system", "content": loan_eligiblity_calculator_prompts.CONVERSATION_PROMPT}
    ]
    for msg in conversation_history[-8:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    state_msg = f"""Current state:
Collected: {json.dumps(validated_fields) if validated_fields else "None"}
Still needed: {json.dumps(missing)}
User said: "{user_input}"

Respond with JSON only:"""
    messages.append({"role": "user", "content": state_msg})

    try:
        response = client.chat.completions.create(
            model=configuration.MODEL_NAME,
            messages=messages,
            temperature=configuration.TEMPERATURE,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)

        # Clean extracted fields through the normalizer (safety net)
        cleaned = {}
        for field, value in (result.get("extracted_fields") or {}).items():
            if field not in required:
                continue
            num = normalize_value(field, value)
            if num is None:
                continue
            cleaned[field] = num

        # Cross-check on the MERGED state (catches income changed after EMI stored)
        merged = {**validated_fields, **cleaned}
        income = merged.get("monthly_income")
        emi = merged.get("existing_emi")
        
        if income is not None and emi is not None and emi > income:
            # Drop whichever was just added that caused the conflict
            if "monthly_income" in cleaned:
                del cleaned["monthly_income"]
                note = " Monthly income must be greater than your existing EMI."
            elif "existing_emi" in cleaned:
                del cleaned["existing_emi"]
                note = " Existing EMI cannot exceed monthly income."
            else:
                note = ""
            result["response"] = (result.get("response") or "") + note
            merged = {**validated_fields, **cleaned}

        return {
            "response": result.get("response") or "Could you please provide the missing details?",
            "extracted_fields": cleaned,
            "all_fields_collected": all(f in merged for f in required),
        }

    except Exception as e:
        print(f"\n[LLM Error: {e}]")
        return {
            "response": "Sorry, I didn't catch that. Could you please repeat?",
            "extracted_fields": {},
            "all_fields_collected": False,
        }


# ---------------------------------------------------------------------------
# Greeting for a new conversation
# ---------------------------------------------------------------------------
def get_initial_greeting():
    client = get_client()
    messages = [
        {"role": "system", "content": loan_eligiblity_calculator_prompts.CONVERSATION_PROMPT},
        {"role": "user", "content": (
            "New conversation. Greet the user and ask for all four fields: "
            "Monthly Income, Existing EMI, Down Payment, Loan Tenure "
            "(in years or months). Keep it short."
        )}
    ]
    try:
        response = client.chat.completions.create(
            model=configuration.MODEL_NAME,
            messages=messages,
            temperature=configuration.TEMPERATURE,
            max_tokens=150,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        return result.get("response", "Hello! Please provide your loan details.")
    except Exception:
        return (
            "Hello! I'm your Loan Eligibility Advisor. Please provide your "
            "Monthly Income, Existing EMI, Down Payment, and Loan Tenure."
        )


# ---------------------------------------------------------------------------
# ANSWER stage — confirm collected fields before backend
# ---------------------------------------------------------------------------
def ask_answer_confirm(validated_fields):
    client = get_client()
    user_msg = (
        f"MODE: confirm\n\nValidated fields:\n"
        f"{json.dumps(validated_fields, indent=2)}\n\n"
        f"Summarize and confirm to user."
    )
    messages = [
        {"role": "system", "content": loan_eligiblity_calculator_prompts.ANSWER_PROMPT},
        {"role": "user", "content": user_msg}
    ]
    try:
        response = client.chat.completions.create(
            model=configuration.MODEL_NAME,
            messages=messages,
            temperature=configuration.TEMPERATURE,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "All details received. Processing your eligibility..."


# ---------------------------------------------------------------------------
# ANSWER stage — explain friend's backend result in natural language
# ---------------------------------------------------------------------------
def ask_answer_explain(backend_result):
    client = get_client()
    user_msg = (
        f"MODE: explain_result\n\nBackend result:\n"
        f"{json.dumps(backend_result, indent=2)}\n\n"
        f"Explain to user."
    )
    messages = [
        {"role": "system", "content": loan_eligiblity_calculator_prompts.ANSWER_PROMPT},
        {"role": "user", "content": user_msg}
    ]
    try:
        response = client.chat.completions.create(
            model=configuration.MODEL_NAME,
            messages=messages,
            temperature=configuration.TEMPERATURE,
            max_tokens=200
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return f"Result: {json.dumps(backend_result)}"