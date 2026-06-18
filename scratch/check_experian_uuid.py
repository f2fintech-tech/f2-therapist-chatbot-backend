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

# Test payload with full UUIDv4 for client_ref_num
payload = {
    "client_ref_num": str(uuid.uuid4()),
    "name": "Rahul Sharma",
    "phone": "9876543210",
    "pan": "ABCDE1234F"
}

print("Payload:", payload)
try:
    response = httpx.post(api_url, json=payload, headers=headers, timeout=10.0)
    print("Status:", response.status_code)
    print("Response:", response.text)
except Exception as e:
    print("Error:", e)
