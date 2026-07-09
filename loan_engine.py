
import csv

FOIR = 0.50
ANNUAL_INTEREST_RATE = 0.08
MONTHS_IN_YEAR = 12


def load_properties(csv_file):
    properties = []
    with open(csv_file, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                properties.append({
                    "id": row["property_id"],
                    "name": row["property_name"],
                    "location": row["location"],
                    "price": float(row["price"])
                })
            except:
                pass
    return properties


def get_user_input():
    income = float(input("Monthly Income: "))
    existing_emi = float(input("Existing EMI: "))
    down_payment = float(input("Down Payment: "))
    years = int(input("Loan Tenure (Years): "))
    return income, existing_emi, down_payment, years


def calculate_foir_limit(income):
    return income * FOIR


def is_high_emi(existing_emi, limit):
    return existing_emi >= limit


def calculate_eligible_emi(income, existing_emi):
    return income * FOIR - existing_emi


def monthly_interest():
    return ANNUAL_INTEREST_RATE / 12


def calculate_loan_amount(emi, rate, months):
    if rate == 0:
        return emi * months
    factor = (1 + rate) ** months
    return emi * ((factor - 1) / (rate * factor))


def calculate_property_budget(loan_amount, down_payment):
    return loan_amount + down_payment


def find_matching_properties(properties, budget):
    matches = []
    for p in properties:
        if p["price"] <= budget:
            matches.append(p)
    matches.sort(key=lambda x: x["price"])
    return matches


def display_properties(properties):
    if not properties:
        print("No matching properties found.")
        return
    print("\nMatching Properties")
    print("-" * 60)
    for p in properties:
        print(f'{p["id"]} | {p["name"]} | {p["location"]} | ₹{p["price"]:,.2f}')


def main():
    csv_file = "sample_property_catalogue.csv"
    properties = load_properties(csv_file)

    income, existing_emi, down_payment, years = get_user_input()

    foir_limit = calculate_foir_limit(income)

    if is_high_emi(existing_emi, foir_limit):
        print("\nLoan Status : High EMI Burden")
        print("Existing EMI exceeds FOIR limit.")
        budget = down_payment
        display_properties(find_matching_properties(properties, budget))
        return

    eligible_emi = calculate_eligible_emi(income, existing_emi)
    months = years * MONTHS_IN_YEAR
    rate = monthly_interest()

    loan_amount = calculate_loan_amount(eligible_emi, rate, months)
    property_budget = calculate_property_budget(loan_amount, down_payment)

    print("\nLoan Status : Eligible")
    print(f"Eligible EMI      : ₹{eligible_emi:,.2f}")
    print(f"Loan Amount       : ₹{loan_amount:,.2f}")
    print(f"Property Budget   : ₹{property_budget:,.2f}")

    display_properties(find_matching_properties(properties, property_budget))


if __name__ == "__main__":
    main()
