import os
from dotenv import load_dotenv

load_dotenv()

# API key format as requested
OPENAI_API_KEY = os.getenv("open_api_key", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_TOKENS = 1024
TEMPERATURE = 0.2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROPERTY_CATALOGUE_CSV = os.path.join(BASE_DIR, "sample_property_catalogue.csv")

# Tenure is stored in years everywhere. User can say "60 months" and it
# converts to 5 years. Engine receives years.
REQUIRED_FIELDS = [
    "monthly_income",
    "existing_emi",
    "down_payment",
    "loan_tenure_years",
]

FIELD_LABELS = {
    "monthly_income": "Monthly Income",
    "existing_emi": "Existing Monthly EMI",
    "down_payment": "Down Payment",
    "loan_tenure_years": "Loan Tenure (years or months)",
}
