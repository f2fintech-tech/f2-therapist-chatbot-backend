#!/usr/bin/env python3
"""
Diagnostic script to test backend connectivity and configuration (Unicode safe version)
"""
import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
BACKEND_URL = "http://localhost:8000"

print("=" * 80)
print("BACKEND DIAGNOSTIC TEST SUITE")
print("=" * 80)

# 1. Check environment variables
print("\n1. ENVIRONMENT VARIABLES CHECK:")
print("-" * 80)
env_vars = {
    "GEMINI_API_KEY": len(os.getenv("GEMINI_API_KEY", "")) > 0,
    "PINECONE_API_KEY": len(os.getenv("PINECONE_API_KEY", "")) > 0,
    "AWS_ACCESS_KEY_ID": len(os.getenv("AWS_ACCESS_KEY_ID", "")) > 0,
    "API_ACCESS_TOKEN": len(os.getenv("API_ACCESS_TOKEN", "")) > 0,
    "ENVIRONMENT": os.getenv("ENVIRONMENT", "not-set"),
    "HOST": os.getenv("HOST", "not-set"),
    "PORT": os.getenv("PORT", "not-set"),
}

for key, value in env_vars.items():
    status = "[OK]" if value else "[MISSING/NOT SET]"
    print(f"{status} {key}: {value}")

# 2. Test backend connectivity
print("\n2. BACKEND CONNECTIVITY TEST:")
print("-" * 80)

try:
    response = requests.get(f"{BACKEND_URL}/", timeout=5)
    print(f"[OK] Backend is responding (Status: {response.status_code})")
    print(f"  Response: {response.json()}")
except requests.exceptions.ConnectionError:
    print(f"[ERR] Cannot connect to backend at {BACKEND_URL}")
    print("  Make sure backend is running: python -m uvicorn src.main:app --reload")
    sys.exit(1)
except Exception as e:
    print(f"[ERR] Error connecting to backend: {e}")
    sys.exit(1)

# 3. Test CORS headers
print("\n3. CORS HEADERS TEST:")
print("-" * 80)

try:
    response = requests.options(
        f"{BACKEND_URL}/api/v1/chat",
        headers={"Origin": "http://localhost:5173"},
        timeout=5
    )
    cors_headers = {
        "Access-Control-Allow-Origin": response.headers.get("Access-Control-Allow-Origin", "NOT SET"),
        "Access-Control-Allow-Methods": response.headers.get("Access-Control-Allow-Methods", "NOT SET"),
        "Access-Control-Allow-Headers": response.headers.get("Access-Control-Allow-Headers", "NOT SET"),
    }
    
    print("CORS Headers received:")
    for header, value in cors_headers.items():
        status = "[OK]" if "NOT SET" not in value else "[ERR]"
        print(f"  {status} {header}: {value}")
        
except Exception as e:
    print(f"[ERR] Error testing CORS: {e}")

# 4. Test health endpoint
print("\n4. HEALTH ENDPOINT TEST:")
print("-" * 80)

try:
    response = requests.get(f"{BACKEND_URL}/health", timeout=5)
    print(f"[OK] Health endpoint is working (Status: {response.status_code})")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"[ERR] Health endpoint failed: {e}")

# 5. Test chat endpoint without auth
print("\n5. CHAT ENDPOINT TEST (No Auth):")
print("-" * 80)

import uuid

test_payload = {
    "message": "Hello, test message",
    "user_id": str(uuid.uuid4()),
}

try:
    response = requests.post(
        f"{BACKEND_URL}/api/v1/chat",
        json=test_payload,
        headers={"Origin": "http://localhost:5173"},
        timeout=5
    )
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("[OK] Chat endpoint is working")
        data = response.json()
        print(f"  Response keys: {list(data.keys())}")
    elif response.status_code == 401:
        print("[ERR] API requires authentication (401 Unauthorized)")
        print(f"  Response: {response.json()}")
    else:
        print(f"[ERR] Unexpected status code: {response.status_code}")
        print(f"  Response: {response.text}")
        
except requests.exceptions.ConnectionError:
    print("[ERR] Cannot connect to backend")
except Exception as e:
    print(f"[ERR] Error testing chat endpoint: {e}")

# 6. Test with API key if configured
api_key = os.getenv("API_ACCESS_TOKEN", "")
if api_key:
    print("\n6. CHAT ENDPOINT TEST (With API Key):")
    print("-" * 80)
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/v1/chat",
            json=test_payload,
            headers={
                "Origin": "http://localhost:5173",
                "Authorization": f"Bearer {api_key}"
            },
            timeout=5
        )
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("[OK] Chat endpoint works with API key")
        else:
            print(f"[ERR] Status code: {response.status_code}")
            print(f"  Response: {response.text}")
            
    except Exception as e:
        print(f"[ERR] Error: {e}")
else:
    print("\n6. CHAT ENDPOINT TEST (With API Key):")
    print("-" * 80)
    print("WARNING: No API_ACCESS_TOKEN configured - skipping auth test")

print("\n" + "=" * 80)
print("DIAGNOSTIC TEST COMPLETE")
print("=" * 80)
