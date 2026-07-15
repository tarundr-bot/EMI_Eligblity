"""
engine.py
---------
Loan Eligibility Engine.

Takes a validated JSON/dict from the LLM layer and returns a JSON/dict
result with eligibility status, EMI, loan amount, property budget, and
matching properties.
"""

import csv
import configuration

FOIR = 0.50
ANNUAL_INTEREST_RATE = 0.08
MONTHS_IN_YEAR = 12


def load_properties(csv_file: str = None) -> list:
    """Read the property catalogue CSV into a list of dicts."""
    csv_file = csv_file or configuration.PROPERTY_CATALOGUE_CSV
    properties = []
    with open(csv_file, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                properties.append({
                    "id": row["property_id"],
                    "name": row["property_name"],
                    "location": row["location"],
                    "price": float(row["price"]),
                })
            except (KeyError, ValueError):
                pass
    return properties


def calculate_foir_limit(income: float) -> float:
    return income * FOIR


def is_high_emi_burden(existing_emi: float, foir_limit: float) -> bool:
    return existing_emi >= foir_limit


def calculate_eligible_emi(income: float, existing_emi: float) -> float:
    return income * FOIR - existing_emi


def calculate_loan_amount(emi: float, months: float) -> float:
    """EMI formula solved for principal, at the fixed annual interest rate."""
    rate = ANNUAL_INTEREST_RATE / MONTHS_IN_YEAR
    if rate == 0:
        return emi * months
    factor = (1 + rate) ** months
    return emi * ((factor - 1) / (rate * factor))


def calculate_property_budget(loan_amount: float, down_payment: float) -> float:
    return loan_amount + down_payment


def find_matching_properties(properties: list, budget: float) -> list:
    matches = [p for p in properties if p["price"] <= budget]
    matches.sort(key=lambda p: p["price"], reverse=True)
    return matches


def compute_eligibility(fields: dict) -> dict:
    """
    Main entry point called by the LLM layer.

    Expected input keys (numbers):
        monthly_income, existing_emi, down_payment, loan_tenure_years

    Returns a dict (JSON-serializable) with the eligibility result.
    """
    required = ["monthly_income", "existing_emi", "down_payment", "loan_tenure_years"]
    missing = [k for k in required if k not in fields]
    if missing:
        return {"error": "Missing fields for engine", "missing": missing}

    income = float(fields["monthly_income"])
    existing_emi = float(fields["existing_emi"])
    down_payment = float(fields["down_payment"])
    years = float(fields["loan_tenure_years"])

    properties = load_properties()
    foir_limit = calculate_foir_limit(income)

    if is_high_emi_burden(existing_emi, foir_limit):
        return {
            "status": "High EMI Burden",
            "reason": "Existing EMI exceeds allowable FOIR (50% of income).",
            "eligible_emi": 0,
            "loan_amount": 0,
            "property_budget": round(down_payment, 2),
            "matching_properties": find_matching_properties(properties, down_payment),
        }

    eligible_emi = calculate_eligible_emi(income, existing_emi)
    months = years * MONTHS_IN_YEAR
    loan_amount = calculate_loan_amount(eligible_emi, months)
    property_budget = calculate_property_budget(loan_amount, down_payment)

    return {
        "status": "Eligible",
        "eligible_emi": round(eligible_emi, 2),
        "loan_amount": round(loan_amount, 2),
        "property_budget": round(property_budget, 2),
        "matching_properties": find_matching_properties(properties, property_budget),
    }
