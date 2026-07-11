# AI Loan Eligibility Calculator — Complete Workflow / Function Call Flow

This document explains the end-to-end workflow and the call chain across the codebase:

- **Entry point / CLI loop:** `main.py`
- **LLM conversation + extraction + normalization:** `llm.py`
- **Backend API call:** `backend.py`
- **Constants & session storage paths:** `configuration.py`
- **LLM prompts (system prompts):** `loan_eligiblity_calculator_prompts.py`

---

## 1) Start: where execution begins

### `main.py` → `__main__`
- File: `main.py`
- How it starts:
  ```py
  if __name__ == "__main__":
      sid = sys.argv[1] if len(sys.argv) > 1 else str(uuid.uuid4())[:8]
      run_pipeline(sid)
  ```
- Meaning:
  - Uses a `session_id` (`sid`) from CLI argument or generates one.
  - Calls **`run_pipeline(session_id)`**.

---

## 2) Session loading + greeting: where conversation state lives

### `main.py` → `run_pipeline(session_id)`
Key responsibilities:
1. Load prior session state from `storage/session_<sid>.json`
2. If no conversation yet, ask LLM for a greeting
3. Repeatedly accept user input
4. Call the LLM once per user message to extract fields
5. When all fields are collected, call backend + then call LLM to explain results

#### 2.1 Session files
Paths are built by `configuration.py`:
- `configuration.session_file(session_id)` → `storage/session_<sid>.json`
- `configuration.backend_input_file(session_id)` → `storage/backend_input_<sid>.json`
- `configuration.backend_output_file(session_id)` → `storage/backend_output_<sid>.json`

#### 2.2 First run: greeting
Inside `run_pipeline`:
- It reads:
  - `validated_fields` (dict)
  - `conversation_history` (list)
- If `conversation_history` is empty:
  1. Calls **`llm.get_initial_greeting()`**
  2. Prints greeting
  3. Appends greeting into `conversation_history`
  4. Saves updated session JSON

---

## 3) Main loop: one LLM call per user message

### `main.py` → while True loop
Pseudo-flow:
1. Read input from terminal:
   ```py
   user_input = input("You : ").strip()
   ```
2. Append user message to `conversation_history` as:
   ```py
   {"role": "user", "content": user_input}
   ```
3. Call:
   **`llm.process_conversation(user_input, validated_fields, conversation_history)`**
4. Receive:
   - `ai_response`
   - `new_fields` (extracted/validated fields)
5. Merge new fields into `validated_fields`
6. Print AI response
7. Append AI response into `conversation_history`
8. Save session progress
9. If all required fields collected → backend stage + explanation stage

#### 3.1 Required fields
From `configuration.py`:
```py
REQUIRED_FIELDS = [
  "monthly_income",
  "existing_emi",
  "down_payment",
  "loan_tenure_years",
]
```
When:
```py
all(f in validated_fields for f in required)
```
becomes true, pipeline ends the conversational collection stage.

---

## 4) LLM stage: `llm.process_conversation()` (the core extraction logic)

### `llm.py` → `process_conversation(user_input, validated_fields, conversation_history)`
This is the central function.
It:
- Builds the messages for the OpenAI chat completion
- Asks the model to output strict JSON
- Parses it
- Normalizes extracted values (safety net)
- Cross-checks for `existing_emi <= monthly_income`
- Returns:
  - `response` (assistant message text)
  - `extracted_fields` (cleaned numeric values)
  - `all_fields_collected`

#### 4.1 Client creation
- Uses **`llm.get_client()`**:
  ```py
  openai.OpenAI(api_key=configuration.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY"))
  ```

#### 4.2 Build LLM prompt/messages
- System message:
  - `loan_eligiblity_calculator_prompts.CONVERSATION_PROMPT`
- Adds last up to **8** conversation entries:
  ```py
  for msg in conversation_history[-8:]:
  ```
- Adds a custom “state” user message containing:
  - `Collected: <validated_fields>`
  - `Still needed: <missing fields>`
  - `User said: "<user_input>"`
  - and instructs: `Respond with JSON only`.

#### 4.3 OpenAI call
- Uses:
  - `model=configuration.MODEL_NAME`
  - `temperature=configuration.TEMPERATURE`
  - `response_format={"type":"json_object"}`

#### 4.4 Parse LLM JSON
- Parses:
  ```py
  result = json.loads(response.choices[0].message.content)
  ```
- Expects `result` to include keys like:
  - `response`
  - `extracted_fields`

#### 4.5 Python-side normalization (safety net)
For each `field, value` in `result["extracted_fields"]`:
- Calls:
  **`normalize_value(field, value)`**
- Only keeps fields where normalized output is not `None`.

Important detail:
- Tenure is expected/returned as **years**.
- If LLM returns months-like input, normalization converts months → years.

#### 4.6 Cross-check: EMI cannot exceed monthly income
After merging:
```py
merged = {**validated_fields, **cleaned}
```
If:
- `income = merged.get("monthly_income")`
- `emi = merged.get("existing_emi")`
- and `emi > income`
Then:
- remove the conflicting newly added field (`monthly_income` or `existing_emi`) from `cleaned`
- append a note onto `result["response"]`

#### 4.7 Return object to `main.py`
`process_conversation` returns:
```json
{
  "response": <assistant text>,
  "extracted_fields": <dict of cleaned numeric fields>,
  "all_fields_collected": <bool>
}
```

Note: In `main.py`, the loop primarily trusts `extracted_fields` and checks completion using `validated_fields`.

---

## 5) Greeting stage vs Answer stages

### 5.1 Greeting: `llm.get_initial_greeting()`
- Called only when session starts with empty conversation history.
- Uses the same `CONVERSATION_PROMPT` system prompt.
- User content tells LLM to greet + ask for all four fields.

### 5.2 Confirm stage: `llm.ask_answer_confirm(validated_fields)`
- Called in `run_backend_and_explain()` right before backend call.
- Uses:
  - `loan_eligiblity_calculator_prompts.ANSWER_PROMPT`m
  - Mode `confirm`
- Generates a short confirm/summarization message.

### 5.3 Explain stage: `llm.ask_answer_explain(backend_result)`
- Called after backend JSON is received.
- Uses:
  - Mode `explain_result`
- LLM explains the backend result in natural language.

---

## 6) Backend stage: where calculation happens outside the LLM

### `main.py` → `run_backend_and_explain(session_id, validated_fields, conversation_history)`
Steps:
1. Prints confirm message from:
   - **`llm.ask_answer_confirm(validated_fields)`**
2. Creates `backend_fields = validated_fields.copy()`
3. Writes backend input JSON:
   - `configuration.backend_input_file(session_id)`
4. Calls backend calculation:
   - **`backend.compute_eligibility(backend_fields)`**
5. Writes backend output JSON:
   - `configuration.backend_output_file(session_id)`
6. If backend response contains `

