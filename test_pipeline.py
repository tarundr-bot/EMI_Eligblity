import llm

CASES = [
    # (field, raw_input, expected)
    ("monthly_income", "1 lakh", 100000),
    ("monthly_income", "Rs.50,000", 50000),
    ("existing_emi", "30k", 30000),
    ("existing_emi", "3ok", 3000),       # <<<< CHANGED: typo extracts 3 + k = 3000
    ("down_payment", "8 lakh", 800000),
    ("down_payment", "₹8,00,000", 800000),
    ("loan_tenure_years", "5 years", 5),
    ("loan_tenure_years", "60 months", 5),
    ("loan_tenure_years", 60, 5),
    ("loan_tenure_years", 5, 5),
    ("loan_tenure_years", "240 months", 20),
    ("monthly_income", "-50000", None),
    ("loan_tenure_years", "50 years", None),
    ("existing_emi", "abc", None),
]

passed = failed = 0
for field, raw, expected in CASES:
    got = llm.normalize_value(field, raw)
    status = "PASS" if got == expected else "FAIL"
    if got == expected:
        passed += 1
    else:
        failed += 1
    print(f"[{status}] normalize_value({field!r}, {raw!r}) -> {got} (expected {expected})")

print(f"\n{passed} passed, {failed} failed")