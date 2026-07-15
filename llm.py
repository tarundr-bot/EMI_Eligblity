import openai
import json
import random
import configuration
import loan_eligiblity_calculator_prompts


def get_client():
    return openai.OpenAI(api_key=configuration.OPENAI_API_KEY)


def _call_llm(system_prompt, user_content, temperature=None, max_tokens=None, json_mode=False):
    """Reusable helper for all LLM calls."""
    client = get_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    kwargs = {
        "model": configuration.MODEL_NAME,
        "messages": messages,
        "temperature": temperature if temperature is not None else configuration.TEMPERATURE,
        "max_tokens": max_tokens or configuration.MAX_TOKENS,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content
    return json.loads(content) if json_mode else content.strip()


# ---------------------------------------------------------------------------
# Prompt 2: Extract raw, unstructured fields from user input
# ---------------------------------------------------------------------------
def extract_raw_fields(user_input, validated_fields=None):
    required = configuration.REQUIRED_FIELDS
    validated_fields = validated_fields or {}
    collected = [f for f in required if f in validated_fields]
    pending = [f for f in required if f not in validated_fields]

    context_msg = (
        f"Already collected: {json.dumps(collected)}\n"
        f"Pending: {json.dumps(pending)}\n\n"
        f"User: \"{user_input}\""
    )
    try:
        return _call_llm(
            loan_eligiblity_calculator_prompts.EXTRACT_PROMPT,
            context_msg,
            temperature=0.0,  # Zero temperature for deterministic extraction
            json_mode=True
        )
    except Exception as e:
        print(f"\n[Extraction Error: {e}]")
        return {}


# ---------------------------------------------------------------------------
# Prompt 3 (Validation): Validate and normalize a single field
# ---------------------------------------------------------------------------
def validate_field(field_name, raw_value, known_monthly_income=None):
    user_content = f"Field: {field_name}\nRaw Value: {raw_value}"
    if known_monthly_income is not None:
        user_content += f"\nKnown monthly_income: {known_monthly_income}"

    try:
        return _call_llm(
            loan_eligiblity_calculator_prompts.VALIDATE_PROMPT,
            user_content,
            temperature=0.0,  # Zero temperature for reliable validation
            json_mode=True
        )
    except Exception as e:
        print(f"\n[Validation Error for {field_name}: {e}]")
        return {
            "field": field_name,
            "valid": False,
            "normalized_value": None,
            "reason": "Could not validate field due to a technical error."
        }

# ---------------------------------------------------------------------------
# Main conversational call: coordinates the modular prompt pipeline.
# Returns {"response": str, "extracted_fields": dict, "all_fields_collected": bool}
# ---------------------------------------------------------------------------
def process_conversation(user_input, validated_fields, conversation_history):
    client = get_client()
    required = configuration.REQUIRED_FIELDS

    # Step 1: Extract raw fields from latest user input (with context of what's already collected)
    extracted = extract_raw_fields(user_input, validated_fields)

    newly_validated = {}
    clarifications = []

    # Validate monthly_income first if it was provided, so it is available as context for EMI checks
    ordered_fields = []
    if "monthly_income" in extracted:
        ordered_fields.append("monthly_income")
    for f in extracted:
        if f != "monthly_income" and f in required:
            ordered_fields.append(f)

    current_monthly_income = validated_fields.get("monthly_income")

    # Step 2: Validate and normalize each extracted field
    for field in ordered_fields:
        raw_val = extracted[field]
        val_result = validate_field(field, raw_val, current_monthly_income)

        if val_result.get("valid"):
            norm_val = val_result.get("normalized_value")
            newly_validated[field] = norm_val
            if field == "monthly_income":
                current_monthly_income = norm_val
        else:
            reason = val_result.get("reason") or f"The value '{raw_val}' for {field} is invalid. Please provide a valid value."
            clarifications.append(reason)

    # Step 3: Python safety net/cross-checks for merged state
    merged = {**validated_fields, **newly_validated}
    income = merged.get("monthly_income")
    emi = merged.get("existing_emi")

    if income is not None and emi is not None and emi > income:
        if "monthly_income" in newly_validated:
            del newly_validated["monthly_income"]
            msg = f"Your monthly income of ₹{income:,.0f} must be greater than your existing EMI of ₹{emi:,.0f}. Could you please re-provide your monthly income?"
            clarifications.append(msg)
        elif "existing_emi" in newly_validated:
            del newly_validated["existing_emi"]
            msg = f"Your existing EMI of ₹{emi:,.0f} cannot exceed your monthly income of ₹{income:,.0f}. Could you please re-provide your existing EMI?"
            clarifications.append(msg)
        merged = {**validated_fields, **newly_validated}

    # If validation errors occurred, return them immediately
    if clarifications:
        return {
            "response": "\n\n".join(clarifications),
            "extracted_fields": newly_validated,
            "all_fields_collected": False
        }

    # Step 4: Check if all required fields are now collected
    all_fields_collected = all(f in merged for f in required)
    if all_fields_collected:
        return {
            "response": "Thank you, all details have been collected.",
            "extracted_fields": newly_validated,
            "all_fields_collected": True
        }

    # Step 5: Call Prompt 1 (CONVERSATION_PROMPT) to generate next response for missing fields
    missing = [f for f in required if f not in merged]
    messages = [
        {"role": "system", "content": loan_eligiblity_calculator_prompts.CONVERSATION_PROMPT}
    ]
    for msg in conversation_history[-8:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    state_msg = f"""Current state:
Collected: {json.dumps(merged) if merged else "None"}
Still needed: {json.dumps(missing)}
User said: "{user_input}"

Provide your friendly response to the user:"""
    messages.append({"role": "user", "content": state_msg})

    try:
        response = client.chat.completions.create(
            model=configuration.MODEL_NAME,
            messages=messages,
            temperature=configuration.TEMPERATURE,
            max_tokens=configuration.MAX_TOKENS
        )
        chat_response = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"\n[Conversation LLM Error: {e}]")
        chat_response = "Could you please provide the missing details?"

    return {
        "response": chat_response,
        "extracted_fields": newly_validated,
        "all_fields_collected": False
    }


# ---------------------------------------------------------------------------
# Greeting for a new conversation (Prompt 1)
# ---------------------------------------------------------------------------
def get_initial_greeting():
    greetings = [
        "Hello! I'm here to assist you with your loan eligibility. Could you please provide your Monthly Income, Existing EMI, Down Payment, and Loan Tenure (in years or months)?",
        "Welcome! Let's check your loan eligibility. To get started, please provide your Monthly Income, Existing EMI, Down Payment, and Loan Tenure.",
        "Hi there! I can help you calculate your eligible loan amount and EMI. Please share your Monthly Income, Existing EMI, Down Payment, and Loan Tenure to begin.",
        "Greetings! Ready to check your loan options? Please provide your Monthly Income, Existing EMI, Down Payment, and Loan Tenure (years or months) so I can calculate your eligibility."
    ]
    return random.choice(greetings)


def ask_answer_confirm(validated_fields):
    income = validated_fields.get("monthly_income", 0)
    emi = validated_fields.get("existing_emi", 0)
    down_payment = validated_fields.get("down_payment", 0)
    tenure = validated_fields.get("loan_tenure_years", 0)
    
    return (
        f"I'm sending off your details for assessment: "
        f"a monthly income of ₹{income:,.0f}, "
        f"existing EMI of ₹{emi:,.0f}, "
        f"a down payment of ₹{down_payment:,.0f}, "
        f"and a loan tenure of {tenure} years."
    )


# ---------------------------------------------------------------------------
# ANSWER stage — explain friend's backend result in natural language (Prompt 4)
# ---------------------------------------------------------------------------
def ask_answer_explain(backend_result):
    user_msg = (
        f"MODE: explain_result\n\nBackend result:\n"
        f"{json.dumps(backend_result, indent=2)}\n\n"
        f"Explain to user."
    )
    try:
        return _call_llm(
            loan_eligiblity_calculator_prompts.ANSWER_PROMPT,
            user_msg
        )
    except Exception:
        return f"Result: {json.dumps(backend_result)}"