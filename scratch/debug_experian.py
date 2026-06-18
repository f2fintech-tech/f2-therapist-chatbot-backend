import os
import httpx
import uuid
from dotenv import load_dotenv

load_dotenv()

api_url    = (os.getenv("EXPERIAN_API_URL") or "").strip()
api_key    = (os.getenv("EXPERIAN_API_KEY") or "").strip()
client_id  = (os.getenv("EXPERIAN_CLIENT_ID") or "").strip()
client_secret = (os.getenv("EXPERIAN_CLIENT_SECRET") or "").strip()

print(f"URL      : {api_url}")
print(f"API Key  : {api_key[:6]}..." if api_key else "API Key  : NOT SET")
print(f"Client ID: {client_id[:6]}..." if client_id else "Client ID: NOT SET")
print(f"Secret   : {client_secret[:6]}..." if client_secret else "Secret   : NOT SET")
print()

# ---- Try 3 different auth formats Experian India uses ----

# Format 1: Separate headers (most common for Digitap)
print("=== FORMAT 1: Separate x-api-key + client-id headers ===")
headers1 = {
    "x-api-key": api_key,
    "client-id": client_id,
    "Content-Type": "application/json"
}
payload = {
    "client_ref_num": str(uuid.uuid4()),
    "name": "Ranjit Kumar Singh",
    "phone": "8271987892"
}
try:
    r = httpx.post(api_url, json=payload, headers=headers1, timeout=15.0)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

print()

# Format 2: Bearer token
print("=== FORMAT 2: Bearer token ===")
headers2 = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}
try:
    r = httpx.post(api_url, json=payload, headers=headers2, timeout=15.0)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

print()

# Format 3: Basic auth (client_id:secret — NOT api_key)
import base64
print("=== FORMAT 3: Basic auth client_id:client_secret ===")
auth_b64 = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
headers3 = {
    "Authorization": f"Basic {auth_b64}",
    "Content-Type": "application/json"
}
try:
    r = httpx.post(api_url, json=payload, headers=headers3, timeout=15.0)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
