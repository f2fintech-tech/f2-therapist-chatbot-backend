import os
import httpx
import base64
import uuid
from dotenv import load_dotenv

# Load env variables
load_dotenv()

api_url = (os.getenv("EXPERIAN_API_URL") or "").strip()

# Send dummy/wrong credentials
raw_creds = "dummy_client_id:dummy_api_key"
encoded_creds = base64.b64encode(raw_creds.encode("utf-8")).decode("utf-8")
headers = {
    "Authorization": f"Basic {encoded_creds}",
    "Content-Type": "application/json"
}

payload = {
    "client_ref_num": str(uuid.uuid4()),
    "name": "Ranjit Kumar Singh",
    "phone": "8271987892"
}

print("Payload:", payload)
try:
    response = httpx.post(api_url, json=payload, headers=headers, timeout=15.0)
    print("Status:", response.status_code)
    print("Response:", response.text)
except Exception as e:
    print("Error:", e)
