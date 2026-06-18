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

# Test different phone/mobile field names
payloads = [
    # 1. mobile
    {
        "client_ref_num": str(uuid.uuid4()),
        "name": "Ranjit Kumar Singh",
        "mobile": "8271987892"
    },
    # 2. mobile_no
    {
        "client_ref_num": str(uuid.uuid4()),
        "name": "Ranjit Kumar Singh",
        "mobile_no": "8271987892"
    },
    # 3. mobileNo
    {
        "client_ref_num": str(uuid.uuid4()),
        "name": "Ranjit Kumar Singh",
        "mobileNo": "8271987892"
    },
    # 4. phone_number
    {
        "client_ref_num": str(uuid.uuid4()),
        "name": "Ranjit Kumar Singh",
        "phone_number": "8271987892"
    },
    # 5. phoneNumber
    {
        "client_ref_num": str(uuid.uuid4()),
        "name": "Ranjit Kumar Singh",
        "phoneNumber": "8271987892"
    },
    # 6. mobNo
    {
        "client_ref_num": str(uuid.uuid4()),
        "name": "Ranjit Kumar Singh",
        "mobNo": "8271987892"
    }
]

for idx, payload in enumerate(payloads):
    print(f"\n--- Testing Payload {idx + 1} ---")
    print("Payload:", payload)
    try:
        response = httpx.post(api_url, json=payload, headers=headers, timeout=15.0)
        print("Status:", response.status_code)
        print("Response:", response.text)
    except Exception as e:
        print("Error:", e)
