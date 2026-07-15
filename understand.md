# 🏦 Loan Eligibility & EMI Advisor — Project Understanding

> A conversational AI chatbot built with **Chainlit** + **OpenAI GPT-4o-mini** that collects user financial details through natural dialogue, validates & normalizes inputs via a multi-stage LLM prompt pipeline, computes home-loan eligibility using a deterministic engine, and recommends matching properties from a CSV catalogue.

---

## 📁 Project Structure

```
LOAN_ELIGIBLITY_CALCULATOR/
│
├── app.py                              # Chainlit frontend — orchestrates the full pipeline
├── engine.py                           # Deterministic loan eligibility calculator
├── llm.py                              # LLM layer — extraction, validation, conversation, explanation
├── configuration.py                    # Centralized config — API keys, model, field definitions
├── loan_eligiblity_calculator_prompts.py   # Prompt aggregator — re-exports all 4 prompts
│
├── conversation_prompt.py              # Prompt 1: Conversational field collection
├── extract_prompt.py                   # Prompt 2: Raw field extraction from user text
├── validate_prompt.py                  # Prompt 3: Field validation & normalization
├── answer_prompt.py                    # Prompt 4: Result confirmation & explanation
│
├── sample_property_catalogue.csv       # 50 properties (id, name, location, price)
├── requirements.txt                    # chainlit, openai, python-dotenv
├── .env                                # OPENAI_API_KEY, OPENAI_MODEL
│
├── public/                             # Static assets served by Chainlit
│   ├── advisor_avatar.png
│   ├── favicon.png
│   └── logo_light.png
│
├── storage/                            # Runtime storage (currently empty)
└── .chainlit/
    └── config.toml                     # Chainlit UI configuration
```

---

## 🔄 Input / Output Structure

### Required User Inputs (4 Fields)

| # | Field Name           | Label                          | Accepted Formats                                     | Normalization Target       |
|---|----------------------|--------------------------------|------------------------------------------------------|----------------------------|
| 1 | `monthly_income`     | Monthly Income                 | `50000`, `50k`, `50 K`, `Rs.50,000`, `1 lakh`       | Plain number (₹)           |
| 2 | `existing_emi`       | Existing Monthly EMI           | `10000`, `10k`, `0`, `no`, `nil`                     | Plain number (₹), ≥ 0      |
| 3 | `down_payment`       | Down Payment                   | `250000`, `2.5 lakh`, `2.5 lakhs`                    | Plain number (₹), ≥ 0      |
| 4 | `loan_tenure_years`  | Loan Tenure (years or months)  | `5 years`, `60 months`, `240 months`, `20`           | Years (integer), 1–30      |

### System Output (Eligibility Result)

```json
{
  "status": "Eligible | High EMI Burden",
  "reason": "...",                        // only if High EMI Burden
  "eligible_emi": 15000.00,               // ₹ per month
  "loan_amount": 1234567.89,              // ₹ total loan principal
  "property_budget": 1484567.89,          // loan_amount + down_payment
  "matching_properties": [                // sorted by price descending
    {
      "id": "P001",
      "name": "Green Valley Apartments",
      "location": "Mumbai",
      "price": 4500000
    }
  ]
}
```

---

## 🧠 Multi-Stage LLM Prompt Pipeline

The system uses **4 specialized prompts**, each sent as a separate LLM call with a focused role:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    LLM PROMPT PIPELINE (4 Stages)                       │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  PROMPT 1 ─ CONVERSATION_PROMPT (conversation_prompt.py)                │
│  ├─ Role: "Loan Eligibility Advisor, a professional financial banker"   │
│  ├─ Goal: Natural conversation to ask for missing fields                │
│  ├─ Input: conversation_history, collected fields, missing fields       │
│  └─ Output: Plain-text friendly response (NO JSON)                     │
│                                                                          │
│  PROMPT 2 ─ EXTRACT_PROMPT (extract_prompt.py)                          │
│  ├─ Role: "Information Extraction stage"                                │
│  ├─ Goal: Extract raw unstructured values from user message             │
│  ├─ Input: Single user message                                          │
│  └─ Output: JSON with raw field values (only mentioned fields)          │
│                                                                          │
│  PROMPT 3 ─ VALIDATE_PROMPT (validate_prompt.py)                        │
│  ├─ Role: "Validation & Normalization stage"                            │
│  ├─ Goal: Normalize raw values → clean numbers, or reject with reason   │
│  ├─ Input: One field name + raw value (+ optional known income)         │
│  └─ Output: JSON {field, valid, normalized_value, reason}               │
│                                                                          │
│  PROMPT 4 ─ ANSWER_PROMPT (answer_prompt.py)                            │
│  ├─ Role: "Answer / Explanation stage"                                  │
│  ├─ Modes: "confirm" (pre-engine) or "explain_result" (post-engine)    │
│  ├─ Input: Validated fields JSON or engine result JSON                  │
│  └─ Output: Plain-text natural-language explanation (NO JSON)           │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Complete Application Flowchart

```mermaid
flowchart TD
    A([🚀 User Opens Chat]) --> B["@on_chat_start<br/>start_session()"]
    B --> B1["Initialize session state<br/>validated_fields = {}<br/>assessment_done = False"]
    B1 --> B2["get_initial_greeting()<br/>(random greeting)"]
    B2 --> B3["Send greeting + progress checklist<br/>(all 4 fields pending)"]
    B3 --> C([💬 User Sends Message])

    C --> D{Message is a<br/>reset keyword?}
    D -- "Yes<br/>(reset/start over/...)" --> B1
    D -- No --> E{assessment_done<br/>== True?}
    E -- Yes --> F["Show: 'Assessment complete'<br/>+ 🔄 New Assessment button"]
    F --> C

    E -- No --> G["Step 1: collect_user_details()<br/>↳ extract_raw_fields() — PROMPT 2<br/>↳ validate_field() — PROMPT 3 (per field)<br/>↳ Python cross-checks (EMI < income)"]

    G --> H["Step 2: merge_new_fields()<br/>Update validated_fields"]
    H --> I["Send AI response to user"]
    I --> J{All 4 fields<br/>collected?}

    J -- No --> K["show_progress()<br/>Checklist: ✅ collected / ⬜ pending"]
    K --> C

    J -- Yes --> L["Step 3: run_eligibility_pipeline()"]
    L --> L1["ask_answer_confirm() — PROMPT 4<br/>'Sending off your details...'"]
    L1 --> L2["engine.compute_eligibility()<br/>(deterministic math)"]
    L2 --> L3{Engine returned<br/>error?}
    L3 -- Yes --> L4["Show: '⚠️ Engine unavailable'"]
    L3 -- No --> L5["ask_answer_explain() — PROMPT 4<br/>Natural-language explanation"]
    L5 --> L6["render_result()<br/>Status card + property table"]
    L6 --> L7["assessment_done = True"]
    L7 --> C
```

---

## ⚙️ Engine Computation Flowchart

```mermaid
flowchart TD
    A["compute_eligibility(fields)"] --> B{All 4 required<br/>fields present?}
    B -- No --> C["Return error:<br/>'Missing fields'"]
    B -- Yes --> D["Parse inputs:<br/>income, existing_emi,<br/>down_payment, years"]
    D --> E["Load properties from CSV<br/>load_properties()"]
    E --> F["Calculate FOIR limit<br/>foir_limit = income × 0.50"]
    F --> G{existing_emi ≥<br/>foir_limit?}

    G -- "Yes (High Burden)" --> H["status = 'High EMI Burden'<br/>eligible_emi = 0<br/>loan_amount = 0<br/>budget = down_payment"]
    H --> I["Find properties ≤ budget"]
    I --> J["Return result"]

    G -- "No (Eligible)" --> K["eligible_emi = income × 0.50 − existing_emi"]
    K --> L["months = years × 12"]
    L --> M["loan_amount = EMI × ((1+r)^n − 1) / (r × (1+r)^n)<br/>where r = 0.08/12"]
    M --> N["property_budget = loan_amount + down_payment"]
    N --> O["Find properties ≤ budget<br/>(sorted by price desc)"]
    O --> P["Return result:<br/>status='Eligible'"]

    style C fill:#ff6b6b,color:#fff
    style H fill:#ffa94d,color:#fff
    style P fill:#51cf66,color:#fff
```

---

## 🔗 Module Dependency Diagram

```mermaid
graph LR
    subgraph "Frontend Layer"
        APP["app.py<br/>(Chainlit)"]
    end

    subgraph "LLM Layer"
        LLM["llm.py"]
        PROMPTS["loan_eligiblity_<br/>calculator_prompts.py"]
        P1["conversation_prompt.py"]
        P2["extract_prompt.py"]
        P3["validate_prompt.py"]
        P4["answer_prompt.py"]
    end

    subgraph "Compute Layer"
        ENGINE["engine.py"]
    end

    subgraph "Config & Data"
        CONFIG["configuration.py"]
        CSV["sample_property_<br/>catalogue.csv"]
        ENV[".env"]
    end

    subgraph "External"
        OPENAI["OpenAI API<br/>(GPT-4o-mini)"]
    end

    APP --> LLM
    APP --> ENGINE
    APP --> CONFIG
    LLM --> PROMPTS
    LLM --> CONFIG
    PROMPTS --> P1
    PROMPTS --> P2
    PROMPTS --> P3
    PROMPTS --> P4
    ENGINE --> CONFIG
    ENGINE --> CSV
    CONFIG --> ENV
    LLM --> OPENAI

    style APP fill:#4c6ef5,color:#fff
    style LLM fill:#7950f2,color:#fff
    style ENGINE fill:#20c997,color:#fff
    style CONFIG fill:#fab005,color:#000
    style OPENAI fill:#ff6b6b,color:#fff
```

---

## 🧩 LLM Call Sequence (Per User Message)

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant A as app.py
    participant L as llm.py
    participant API as OpenAI API
    participant E as engine.py
    participant CSV as property_catalogue.csv

    U->>A: User message
    A->>A: Check reset keywords
    A->>A: Check assessment_done

    rect rgb(240, 240, 255)
        Note over A,API: Stage 1 — Field Extraction
        A->>L: collect_user_details(input, fields, history)
        L->>L: extract_raw_fields(input)
        L->>API: EXTRACT_PROMPT + user message
        API-->>L: JSON {field: raw_value, ...}
    end

    rect rgb(255, 245, 235)
        Note over L,API: Stage 2 — Validation (per field)
        loop For each extracted field
            L->>L: validate_field(name, raw_val, income)
            L->>API: VALIDATE_PROMPT + field data
            API-->>L: JSON {valid, normalized_value, reason}
        end
    end

    rect rgb(235, 255, 240)
        Note over L,A: Stage 3 — Cross-Checks
        L->>L: Python safety net<br/>(EMI < income check)
    end

    alt Fields still missing
        rect rgb(245, 240, 255)
            Note over L,API: Stage 4 — Conversational Response
            L->>API: CONVERSATION_PROMPT + history + state
            API-->>L: Friendly text asking for missing fields
        end
        L-->>A: {response, extracted_fields}
        A->>U: AI response + progress checklist
    else All 4 fields collected
        L-->>A: {response, extracted_fields, all_collected=true}

        rect rgb(255, 240, 240)
            Note over A,API: Stage 5 — Confirmation
            A->>L: ask_answer_confirm(fields)
            L-->>A: "Sending off your details..."
            A->>U: Confirmation message
        end

        rect rgb(220, 255, 220)
            Note over A,CSV: Stage 6 — Engine Computation
            A->>E: compute_eligibility(fields)
            E->>CSV: load_properties()
            CSV-->>E: Property list
            E->>E: FOIR → EMI → Loan → Budget → Match
            E-->>A: Eligibility result JSON
        end

        rect rgb(255, 245, 235)
            Note over A,API: Stage 7 — Explanation
            A->>L: ask_answer_explain(result)
            L->>API: ANSWER_PROMPT + result JSON
            API-->>L: Natural-language explanation
            L-->>A: Explanation text
        end

        A->>U: Explanation + result card + property table
    end
```

---

## 📐 EMI & Loan Calculation Formula

```
┌───────────────────────────────────────────────────────────────────┐
│                    FINANCIAL FORMULAS                             │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Constants:                                                       │
│    FOIR (Fixed Obligation to Income Ratio) = 0.50 (50%)          │
│    Annual Interest Rate = 8% (0.08)                               │
│    Monthly Interest Rate (r) = 0.08 / 12 = 0.006667              │
│                                                                   │
│  Step 1: FOIR Limit                                              │
│  ┌─────────────────────────────────────────────┐                 │
│  │ foir_limit = monthly_income × 0.50          │                 │
│  └─────────────────────────────────────────────┘                 │
│                                                                   │
│  Step 2: Eligible EMI                                            │
│  ┌─────────────────────────────────────────────┐                 │
│  │ eligible_emi = foir_limit − existing_emi    │                 │
│  │             = (income × 0.50) − existing_emi│                 │
│  └─────────────────────────────────────────────┘                 │
│                                                                   │
│  Step 3: Loan Amount (Present Value of Annuity)                  │
│  ┌─────────────────────────────────────────────┐                 │
│  │                    (1 + r)^n − 1             │                 │
│  │ loan_amount = EMI × ───────────────          │                 │
│  │                     r × (1 + r)^n            │                 │
│  │                                               │                 │
│  │ where: r = 0.08/12, n = tenure_years × 12   │                 │
│  └─────────────────────────────────────────────┘                 │
│                                                                   │
│  Step 4: Property Budget                                         │
│  ┌─────────────────────────────────────────────┐                 │
│  │ property_budget = loan_amount + down_payment │                 │
│  └─────────────────────────────────────────────┘                 │
│                                                                   │
│  Step 5: Property Matching                                       │
│  ┌─────────────────────────────────────────────┐                 │
│  │ matching = [p for p in catalogue             │                 │
│  │            if p.price ≤ property_budget]     │                 │
│  │ sorted by price (descending)                 │                 │
│  └─────────────────────────────────────────────┘                 │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### Worked Example

```
┌─────────────────────────────────────────────────────────────────┐
│  INPUT                                                           │
│    monthly_income    = ₹1,00,000                                │
│    existing_emi      = ₹10,000                                  │
│    down_payment      = ₹5,00,000                                │
│    loan_tenure_years = 20                                        │
├─────────────────────────────────────────────────────────────────┤
│  CALCULATION                                                     │
│    foir_limit    = 1,00,000 × 0.50          = ₹50,000           │
│    eligible_emi  = 50,000 − 10,000          = ₹40,000           │
│    r = 0.08/12 = 0.006667                                       │
│    n = 20 × 12  = 240 months                                    │
│    factor = (1.006667)^240 = 4.9268                              │
│    loan_amount = 40,000 × (4.9268−1)/(0.006667×4.9268)          │
│               = 40,000 × 3.9268 / 0.03285                       │
│               ≈ ₹47,82,147                                       │
│    budget = 47,82,147 + 5,00,000            ≈ ₹52,82,147        │
├─────────────────────────────────────────────────────────────────┤
│  OUTPUT                                                          │
│    status          = "Eligible"                                  │
│    eligible_emi    = ₹40,000/month                               │
│    loan_amount     ≈ ₹47,82,147                                  │
│    property_budget ≈ ₹52,82,147                                  │
│    matching props  = All properties with price ≤ ₹52,82,147     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛡️ Validation & Normalization Pipeline

```mermaid
flowchart TD
    A["User types: 'income 3ok, emi 10k,<br/>down 2.5 lacs, tenure 240 months'"] --> B["PROMPT 2: EXTRACT_PROMPT"]

    B --> C["Extracted raw JSON:<br/>{monthly_income: '3ok',<br/>existing_emi: '10k',<br/>down_payment: '2.5 lacs',<br/>loan_tenure_years: '240 months'}"]

    C --> D["PROMPT 3: VALIDATE_PROMPT<br/>(called once per field)"]

    D --> D1["monthly_income: '3ok'<br/>→ typo fix: 'o'→'0' → '30k'<br/>→ normalize: 30000<br/>→ ✅ valid (≥ 1000)"]

    D --> D2["existing_emi: '10k'<br/>→ normalize: 10000<br/>→ ✅ valid (≤ income)"]

    D --> D3["down_payment: '2.5 lacs'<br/>→ slang: 'lacs'→lakhs<br/>→ normalize: 250000<br/>→ ✅ valid (≥ 0)"]

    D --> D4["loan_tenure_years: '240 months'<br/>→ convert: 240/12 = 20 years<br/>→ ✅ valid (1–30 range)"]

    D1 --> E["Python Cross-Check:<br/>existing_emi (10000) < income (30000)?"]
    D2 --> E
    D3 --> E
    D4 --> E
    E -- "✅ Pass" --> F["All fields validated<br/>→ Proceed to engine"]
    E -- "❌ Fail" --> G["Remove invalid field<br/>→ Ask user to re-provide"]

    style A fill:#e3f2fd
    style F fill:#c8e6c9
    style G fill:#ffcdd2
```

---

## 🏗️ Session State Machine

```mermaid
stateDiagram-v2
    [*] --> Collecting: on_chat_start

    state Collecting {
        [*] --> WaitingForInput
        WaitingForInput --> Extracting: User message
        Extracting --> Validating: Raw fields extracted
        Validating --> CrossChecking: Fields normalized
        CrossChecking --> WaitingForInput: Fields missing or invalid
        CrossChecking --> AllCollected: All 4 fields valid
    }

    AllCollected --> Confirming: ask_answer_confirm()
    Confirming --> Computing: compute_eligibility()
    Computing --> Explaining: ask_answer_explain()
    Explaining --> Done: render_result()

    Done --> Collecting: "New Assessment" / reset keyword
    Done --> Done: Any other message

    state Done {
        [*] --> ShowResult
        ShowResult --> PromptReset: "Assessment complete"
    }
```

---

## 📦 Data Structures

### Session Variables (Chainlit `cl.user_session`)

```
┌─────────────────────────┬──────────────────────────────────────────────────┐
│ Key                      │ Type & Description                              │
├─────────────────────────┼──────────────────────────────────────────────────┤
│ validated_fields         │ dict — Collected & validated user inputs        │
│                          │   e.g. {"monthly_income": 50000, ...}          │
├─────────────────────────┼──────────────────────────────────────────────────┤
│ assessment_done          │ bool — True after eligibility result rendered   │
├─────────────────────────┼──────────────────────────────────────────────────┤
│ conversation_history     │ list[dict] — Chat history for LLM context      │
│                          │   [{"role": "user"|"assistant", "content": ..}] │
└─────────────────────────┴──────────────────────────────────────────────────┘
```

### LLM Response Structure (`process_conversation` return)

```
┌─────────────────────────┬──────────────────────────────────────────────────┐
│ Key                      │ Type & Description                              │
├─────────────────────────┼──────────────────────────────────────────────────┤
│ response                 │ str — Text to display to user                   │
├─────────────────────────┼──────────────────────────────────────────────────┤
│ extracted_fields         │ dict — Newly validated fields from this turn    │
├─────────────────────────┼──────────────────────────────────────────────────┤
│ all_fields_collected     │ bool — True if all 4 fields now available       │
└─────────────────────────┴──────────────────────────────────────────────────┘
```

### Validation Result Structure (`validate_field` return)

```json
{
  "field": "monthly_income",
  "valid": true,
  "normalized_value": 50000,
  "reason": null
}
```

```json
{
  "field": "loan_tenure_years",
  "valid": false,
  "normalized_value": null,
  "reason": "The tenure value '-5' is negative. Could you please provide a valid loan tenure between 1 and 30 years? For example: '10 years' or '120 months'."
}
```

---

## 🗂️ Property Catalogue Structure

```
sample_property_catalogue.csv (50 properties)
┌──────────────┬─────────────────────────────┬───────────────────┬────────────┐
│ property_id  │ property_name               │ location          │ price (₹)  │
├──────────────┼─────────────────────────────┼───────────────────┼────────────┤
│ P001         │ Green Valley Apartments     │ Mumbai            │ 45,00,000  │
│ P002         │ Sunrise Heights             │ Pune              │ 32,00,000  │
│ P003         │ Lakeview Residency          │ Bangalore         │ 58,00,000  │
│ ...          │ ...                         │ ...               │ ...        │
│ P036         │ Golden Palm Villas          │ Goa               │ 95,00,000  │
│ P050         │ West End Heights            │ Navi Mumbai       │ 57,00,000  │
├──────────────┴─────────────────────────────┴───────────────────┴────────────┤
│ Price Range: ₹19,00,000 (P012) — ₹95,00,000 (P036)                        │
│ Locations: 38 unique cities across India                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔌 Configuration & Environment

```
┌───────────────────────────────────────────────────────┐
│  .env                                                  │
│  ├─ OPENAI_API_KEY = <your-key>                       │
│  └─ OPENAI_MODEL   = gpt-4o-mini                     │
│                                                        │
│  configuration.py                                      │
│  ├─ MODEL_NAME     = gpt-4o-mini (from env)           │
│  ├─ MAX_TOKENS     = 1024                              │
│  ├─ TEMPERATURE    = 0.2                               │
│  ├─ FOIR (engine)  = 0.50 (50%)                       │
│  ├─ Interest Rate  = 8% per annum                      │
│  └─ REQUIRED_FIELDS = [monthly_income,                │
│                         existing_emi,                  │
│                         down_payment,                  │
│                         loan_tenure_years]             │
└───────────────────────────────────────────────────────┘
```

---

## 🚀 How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your OpenAI API key in .env
#    OPENAI_API_KEY=sk-...

# 3. Run the Chainlit app
chainlit run app.py
```

---

## 📋 Reset Keywords

The user can restart the assessment at any time by typing any of these:

| Keyword            | Action                       |
|--------------------|------------------------------|
| `new assessment`   | Clears session, starts over  |
| `start over`       | Clears session, starts over  |
| `reset`            | Clears session, starts over  |
| `recalculate`      | Clears session, starts over  |
| `new check`        | Clears session, starts over  |
| `start again`      | Clears session, starts over  |
| `restart`          | Clears session, starts over  |

Additionally, a **🔄 New Assessment** action button appears after the result is rendered.

---

## 🔒 Safety & Edge Cases

```
┌─────────────────────────────────────────────────────────────────┐
│  VALIDATION GUARDS                                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  LLM-Level (VALIDATE_PROMPT):                                    │
│  ├─ Negative numbers → rejected                                 │
│  ├─ monthly_income < ₹1,000 → rejected                         │
│  ├─ existing_emi > monthly_income → rejected                    │
│  ├─ Non-numeric input → rejected                                │
│  ├─ Tenure outside 1–30 years → rejected                        │
│  └─ Typo correction: 'o'/'O' → '0' (e.g., "3ok" → "30k")     │
│                                                                   │
│  Python-Level (llm.py cross-checks):                             │
│  ├─ If EMI > income after merge → remove conflicting field      │
│  └─ Ask user to re-provide the problematic value                 │
│                                                                   │
│  Engine-Level (engine.py):                                       │
│  ├─ Missing fields → return error dict                           │
│  └─ EMI ≥ FOIR limit → "High EMI Burden" (not rejected)        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎨 UI Components (Chainlit)

```mermaid
graph TD
    subgraph "Chat Interface"
        GREET["🏦 Greeting Message<br/>(with advisor avatar)"]
        PROGRESS["📊 Progress Checklist<br/>✅ Collected / ⬜ Pending"]
        CONVO["💬 Conversational Responses<br/>(asking for missing fields)"]
        CONFIRM["📋 Confirmation Message<br/>(summarizing collected data)"]
        EXPLAIN["📝 Explanation<br/>(natural-language result)"]
        CARD["📊 Result Card<br/>(status + EMI + loan + budget table)"]
        PROPS["🏠 Property Table<br/>(matching properties)"]
        ACTION["🔄 New Assessment Button"]
    end

    GREET --> PROGRESS
    PROGRESS --> CONVO
    CONVO --> PROGRESS
    CONVO --> CONFIRM
    CONFIRM --> EXPLAIN
    EXPLAIN --> CARD
    CARD --> PROPS
    PROPS --> ACTION

    style GREET fill:#4c6ef5,color:#fff
    style CARD fill:#20c997,color:#fff
    style ACTION fill:#fab005,color:#000
```

---

## 📊 End-to-End Data Flow (ASCII)

```
 USER                    APP.PY                 LLM.PY                 OPENAI API              ENGINE.PY           CSV
  │                        │                      │                      │                       │                  │
  │  "income 50k, emi 0"  │                      │                      │                       │                  │
  │───────────────────────>│                      │                      │                       │                  │
  │                        │  extract_raw_fields()│                      │                       │                  │
  │                        │─────────────────────>│  EXTRACT_PROMPT      │                       │                  │
  │                        │                      │─────────────────────>│                       │                  │
  │                        │                      │<─────────────────────│                       │                  │
  │                        │                      │  {"monthly_income":  │                       │                  │
  │                        │                      │   "50k",             │                       │                  │
  │                        │                      │   "existing_emi":"0"}│                       │                  │
  │                        │                      │                      │                       │                  │
  │                        │  validate_field() ×2 │                      │                       │                  │
  │                        │─────────────────────>│  VALIDATE_PROMPT ×2  │                       │                  │
  │                        │                      │─────────────────────>│                       │                  │
  │                        │                      │<─────────────────────│                       │                  │
  │                        │                      │  {valid:true,        │                       │                  │
  │                        │                      │   norm:50000}        │                       │                  │
  │                        │                      │  {valid:true,        │                       │                  │
  │                        │                      │   norm:0}            │                       │                  │
  │                        │                      │                      │                       │                  │
  │                        │  (2 of 4 fields)     │                      │                       │                  │
  │                        │─────────────────────>│  CONVERSATION_PROMPT │                       │                  │
  │                        │                      │─────────────────────>│                       │                  │
  │                        │                      │<─────────────────────│                       │                  │
  │                        │                      │  "Great! Now I need  │                       │                  │
  │                        │                      │   your down payment  │                       │                  │
  │                        │                      │   and loan tenure."  │                       │                  │
  │  response + checklist  │                      │                      │                       │                  │
  │<───────────────────────│                      │                      │                       │                  │
  │                        │                      │                      │                       │                  │
  │  "dp 5 lakh 20 years"  │                      │                      │                       │                  │
  │───────────────────────>│                      │                      │                       │                  │
  │                        │  [extract + validate] │                     │                       │                  │
  │                        │─────────────────────>│─────────────────────>│                       │                  │
  │                        │                      │<─────────────────────│                       │                  │
  │                        │                      │                      │                       │                  │
  │                        │  ALL 4 FIELDS ✅      │                      │                       │                  │
  │                        │                      │                      │                       │                  │
  │  confirmation msg      │  ask_answer_confirm()│                      │                       │                  │
  │<───────────────────────│                      │                      │                       │                  │
  │                        │                      │                      │  compute_eligibility() │                  │
  │                        │──────────────────────│──────────────────────│──────────────────────>│  load_properties()│
  │                        │                      │                      │                       │─────────────────>│
  │                        │                      │                      │                       │<─────────────────│
  │                        │                      │                      │                       │  FOIR→EMI→Loan   │
  │                        │                      │                      │                       │  →Budget→Match   │
  │                        │<─────────────────────│──────────────────────│───────────────────────│                  │
  │                        │                      │                      │                       │                  │
  │                        │  ask_answer_explain() │                     │                       │                  │
  │                        │─────────────────────>│  ANSWER_PROMPT       │                       │                  │
  │                        │                      │─────────────────────>│                       │                  │
  │                        │                      │<─────────────────────│                       │                  │
  │                        │                      │                      │                       │                  │
  │  explanation +         │                      │                      │                       │                  │
  │  result card +         │                      │                      │                       │                  │
  │  property table +      │                      │                      │                       │                  │
  │  🔄 New Assessment     │                      │                      │                       │                  │
  │<───────────────────────│                      │                      │                       │                  │
  │                        │                      │                      │                       │                  │
```

---

> **Generated for**: Loan Eligibility & EMI Advisor project  
> **Last updated**: July 2026
