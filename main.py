import json
import uuid
import sys

import configuration
import llm
import backend


def save_json(path: str, data: dict) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_json(path: str) -> dict:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def run_pipeline(session_id: str) -> None:

    print("=" * 50)
    print("   AI Loan Eligibility Calculator")
    print("=" * 50)

    existing = load_json(configuration.session_file(session_id))
    validated_fields = existing.get("validated_fields", {})
    conversation_history = existing.get("conversation_history", [])
    required = configuration.REQUIRED_FIELDS

    print(f"\n(session: {session_id})\n")

    # Greeting
    if not conversation_history:
        greeting = llm.get_initial_greeting()
        print(f"AI :\n{greeting}\n")
        conversation_history.append({"role": "assistant", "content": greeting})
        save_json(configuration.session_file(session_id), {
            "validated_fields": validated_fields,
            "conversation_history": conversation_history
        })

    # If already have all fields, skip to backend
    if all(f in validated_fields for f in required):
        print("All fields already collected. Processing...\n")
        run_backend_and_explain(session_id, validated_fields, conversation_history)
        return

    # Single conversational loop
    while True:
        user_input = input("You : ").strip()
        if not user_input:
            continue

        conversation_history.append({"role": "user", "content": user_input})

        # One LLM call handles everything
        result = llm.process_conversation(
            user_input=user_input,
            validated_fields=validated_fields,
            conversation_history=conversation_history
        )

        ai_response = result["response"]
        new_fields = result["extracted_fields"]

        # Merge new fields
        validated_fields.update(new_fields)

        # Print AI response
        print(f"\nAI :\n{ai_response}\n")

        conversation_history.append({"role": "assistant", "content": ai_response})

        # Save progress
        save_json(configuration.session_file(session_id), {
            "validated_fields": validated_fields,
            "conversation_history": conversation_history
        })

        # Check if all fields collected
        if all(f in validated_fields for f in required):
            run_backend_and_explain(session_id, validated_fields, conversation_history)
            break


def run_backend_and_explain(session_id, validated_fields, conversation_history):
    """Confirm → Send to backend → Show result → Explain in natural language."""

    print(f"AI :\n{llm.ask_answer_confirm(validated_fields)}\n")

    # Tenure is already in years — send fields to backend as-is
    backend_fields = validated_fields.copy()

    print("-" * 50)
    print("Processing...\n")

    input_path = configuration.backend_input_file(session_id)
    save_json(input_path, backend_fields)
    print(f"Input JSON: {input_path}")
    print(json.dumps(backend_fields, indent=2))
    print()

#result need to be taken
    result = backend.compute_eligibility(backend_fields)

    output_path = configuration.backend_output_file(session_id)
    save_json(output_path, result)
    print(f"Backend Output: {output_path}")
    print(json.dumps(result, indent=2))
    print("-" * 50)

    # Explain the friend's result in natural language
    if "error" in result:
        print(f"\nAI :\nSorry, the eligibility service is unavailable right now. "
              f"Your details are saved — please try again later.\n")
    else:
        print(f"\nAI :\n{llm.ask_answer_explain(result)}\n")

    # Save final session
    save_json(configuration.session_file(session_id), {
        "validated_fields": validated_fields,
        "backend_result": result,
        "conversation_history": conversation_history
    })


if __name__ == "__main__":
    sid = sys.argv[1] if len(sys.argv) > 1 else str(uuid.uuid4())[:8]
    try:
        run_pipeline(sid)
    except KeyboardInterrupt:
        print("\n\n(Session saved. Run again to resume.)")
    except Exception as e:
        print(f"\nError: {e}")