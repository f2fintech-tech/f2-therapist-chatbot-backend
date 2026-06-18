import os
import httpx
import base64
import uuid
from dotenv import load_dotenv

# Load env variables
load_dotenv()

api_url = (os.getenv("EXPERIAN_API_URL") or "").strip()
api_key = (os.getenv("EXPERIAN_API_KEY") or "").strip()
client_id = (os.getenv("EXPERIAN_CLIENT_ID") or "").strip()

raw_creds = f"{client_id}:{api_key}"
encoded_creds = base64.b64encode(raw_creds.encode("utf-8")).decode("utf-8")
headers = {
    "Authorization": f"Basic {encoded_creds}",
    "Content-Type": "application/json"
}

# Test different payloads
payloads = [
    # Payload A: including client_ref_num
    {
        "client_ref_num": str(uuid.uuid4())[:20],
        "name": "Rahul Sharma",
        "phone": "9876543210",
        "pan": "ABCDE1234F"
    },
    # Payload B: including client_ref_num and mobile instead of phone
    {
        "client_ref_num": str(uuid.uuid4())[:20],
        "name": "Rahul Sharma",
        "mobile": "9876543210",
        "pan": "ABCDE1234F"
    },
    # Payload C: using client_ref_no
    {
        "client_ref_no": str(uuid.uuid4())[:20],
        "name": "Rahul Sharma",
        "phone": "9876543210",
        "pan": "ABCDE1234F"
    },
    # Payload D: basic payload with only client_ref_num and pan and phone
    {
        "client_ref_num": str(uuid.uuid4())[:20],
        "pan": "ABCDE1234F",
        "phone": "9876543210"
    }
]

for idx, payload in enumerate(payloads):
    print(f"\n--- Testing Payload {idx + 1} ---")
    print("Payload:", payload)
    try:
        response = httpx.post(api_url, json=payload, headers=headers, timeout=10.0)
        print("Status:", response.status_code)
        print("Response:", response.text)
    except Exception as e:
        print("Error:", e)
