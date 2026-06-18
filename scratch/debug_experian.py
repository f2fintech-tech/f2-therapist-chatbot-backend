import os
import httpx
import uuid
import base64
import time
from dotenv import load_dotenv

load_dotenv()

api_url   = (os.getenv("EXPERIAN_API_URL") or "").strip()
api_key   = (os.getenv("EXPERIAN_API_KEY") or "").strip()
client_id = (os.getenv("EXPERIAN_CLIENT_ID") or "").strip()

auth_b64 = base64.b64encode(f"{client_id}:{api_key}".encode()).decode()
headers = {"Authorization": f"Basic {auth_b64}", "Content-Type": "application/json"}

# Numeric client_ref_num based on millisecond timestamp (commonly what Digitap expects)
numeric_ref = str(int(time.time() * 1000))

payloads = [
    # Test 1: numeric client_ref_num (most likely fix)
    {
        "label": "Numeric client_ref_num, no dob",
        "payload": {
            "client_ref_num": numeric_ref,
            "name": "Jitender Singh",
            "mobile": "7056405605",
            "consent": "Y"
        }
    },
    # Test 2: numeric ref + dob (DDMMYYYY — common Digitap requirement)
    {
        "label": "Numeric client_ref_num + dob DDMMYYYY",
        "payload": {
            "client_ref_num": str(int(time.time() * 1000) + 1),
            "name": "Jitender Singh",
            "mobile": "7056405605",
            "dob": "01011990",
            "consent": "Y"
        }
    },
    # Test 3: numeric ref + dob in YYYY-MM-DD
    {
        "label": "Numeric client_ref_num + dob YYYY-MM-DD",
        "payload": {
            "client_ref_num": str(int(time.time() * 1000) + 2),
            "name": "Jitender Singh",
            "mobile": "7056405605",
            "dob": "1990-01-01",
            "consent": "Y"
        }
    },
    # Test 4: numeric ref + pan (no dob)
    {
        "label": "Numeric client_ref_num + pan, no dob",
        "payload": {
            "client_ref_num": str(int(time.time() * 1000) + 3),
            "name": "Jitender Singh",
            "mobile": "7056405605",
            "pan": "ABRPK3782D",
            "consent": "Y"
        }
    },
]

for test in payloads:
    print(f"\n=== {test['label']} ===")
    print(f"Payload: {test['payload']}")
    try:
        r = httpx.post(api_url, json=test["payload"], headers=headers, timeout=15.0)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text[:800]}")
    except Exception as e:
        print(f"Error: {e}")
