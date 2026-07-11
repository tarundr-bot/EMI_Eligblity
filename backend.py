import requests
import json


# Friend's backend API URL - change this to your friend's actual endpoint
BACKEND_URL = "http://localhost:5000/compute_eligibility"
# Example: "https://friend-server.com/api/eligibility"


def compute_eligibility(fields: dict) -> dict:
    """
    Send validated fields to friend's backend API.
    Friend calculates and returns eligibility result.
    """
    try:
        response = requests.post(
            BACKEND_URL,
            json=fields,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to backend at {BACKEND_URL}")
        return {"error": "Backend server not running"}
    except requests.exceptions.Timeout:
        print("❌ Backend request timed out")
        return {"error": "Request timed out"}
    except Exception as e:
        print(f"❌ Backend error: {e}")
        return {"error": str(e)}


    