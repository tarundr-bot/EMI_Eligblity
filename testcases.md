Test Cases
TC1 — All fields in one message (Happy Path)
Input:
my monthly income is 1 lakh, emi is 30k, down payment is 8 lakh, tenure 5 years

Expected: AI confirms all fields and triggers backend.
JSON Output: {"monthly_income": 100000, "existing_emi": 30000, "down_payment": 800000, "loan_tenure_years": 5}

TC2 — Fields one at a time
Inputs: 1 lakh → 30000 → 8 lakh → 5 years

TC3 — Tenure in months
Input: income 80000, emi 10000, down payment 5 lakh, 240 months
Expected: "loan_tenure_years": 20

TC4 — Ambiguous tenure number
Input: ... tenure 60 → Should convert to 5 years

TC5 — Typos and informal language
Input: my motnhly income is 1lakh nd emi is 3ok, dp 8lakh, 5yrs

TC6 — Off-topic question
Input: who is the pm of india
Expected: Polite refusal + redirect to loan eligibility

TC7 — Small talk first
Inputs: hello → how are you → loan details

TC8 — Invalid values (Negative Income)
Input: income -50000, emi 30k, down payment 8 lakh, 5 years
Expected: Only negative income rejected; other fields stored.

TC9 — EMI > Income validation
Input: income 50000, emi 80000, down payment 2 lakh, 5 years
Expected: EMI rejected with explanation.

TC10 — Session Resume
Run python main.py test10
Give only income + EMI, then type exit
Run python main.py test10 again
Expected: AI resumes and asks only for remaining fields.
Backend Integration
The system saves structured input to storage/backend_input_<session_id>.json
Your friend's backend should read this file or receive the dict directly
Expected output format from backend.compute_eligibility() is flexible — the LLM will explain whatever keys are returned
Tenure is always sent in years (loan_tenure_years)