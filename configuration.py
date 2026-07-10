import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL_NAME = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
MAX_TOKENS = 1024
TEMPERATURE = 0.2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
os.makedirs(STORAGE_DIR, exist_ok=True)

def session_file(session_id: str) -> str:
    return os.path.join(STORAGE_DIR, f"session_{session_id}.json")

def backend_input_file(session_id: str) -> str:
    return os.path.join(STORAGE_DIR, f"backend_input_{session_id}.json")

def backend_output_file(session_id: str) -> str:
    return os.path.join(STORAGE_DIR, f"backend_output_{session_id}.json")

# Tenure is stored in years everywhere. User can say "60 months" and it
# converts to 5 years. Backend receives years.
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