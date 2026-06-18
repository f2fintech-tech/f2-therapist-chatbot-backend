import os
import httpx
import base64
from dotenv import load_dotenv

# Load env variables
load_dotenv()

api_url = (os.getenv("EXPERIAN_API_URL") or "").strip()
api_key = (os.getenv("EXPERIAN_API_KEY") or "").strip()
client_id = (os.getenv("EXPERIAN_CLIENT_ID") or "").strip()

print("API URL:", api_url)
print("API Key:", api_key)
print("Client ID:", client_id)

payload = {
    "name": "Rahul Sharma",
    "phone": "9876543210",
    "pan": "ABCDE1234F"
}

# Test 1: Current Header Format
headers_1 = {
    "Authorization": f"Bearer {api_key}",
    "Client-ID": client_id,
    "Content-Type": "application/json"
}
print("\n--- Test 1: Bearer Authorization + Client-ID ---")
try:
    response = httpx.post(api_url, json=payload, headers=headers_1, timeout=10.0)
    print("Status:", response.status_code)
    print("Response:", response.text)
except Exception as e:
    print("Error:", e)

# Test 2: Basic Auth Format (Client-ID as user, API key as password)
raw_creds = f"{client_id}:{api_key}"
encoded_creds = base64.b64encode(raw_creds.encode("utf-8")).decode("utf-8")
headers_2 = {
    "Authorization": f"Basic {encoded_creds}",
    "Content-Type": "application/json"
}
print("\n--- Test 2: Basic Authorization (client_id:api_key) ---")
try:
    response = httpx.post(api_url, json=payload, headers=headers_2, timeout=10.0)
    print("Status:", response.status_code)
    print("Response:", response.text)
except Exception as e:
    print("Error:", e)

# Test 3: Basic Auth with API-Key as username and empty password
raw_creds_3 = f"{api_key}:"
encoded_creds_3 = base64.b64encode(raw_creds_3.encode("utf-8")).decode("utf-8")
headers_3 = {
    "Authorization": f"Basic {encoded_creds_3}",
    "Content-Type": "application/json"
}
print("\n--- Test 3: Basic Authorization (api_key:) ---")
try:
    response = httpx.post(api_url, json=payload, headers=headers_3, timeout=10.0)
    print("Status:", response.status_code)
    print("Response:", response.text)
except Exception as e:
    print("Error:", e)

# Test 4: Custom api-key header
headers_4 = {
    "api-key": api_key,
    "Client-ID": client_id,
    "Content-Type": "application/json"
}
print("\n--- Test 4: Custom api-key header + Client-ID ---")
try:
    response = httpx.post(api_url, json=payload, headers=headers_4, timeout=10.0)
    print("Status:", response.status_code)
    print("Response:", response.text)
except Exception as e:
    print("Error:", e)
