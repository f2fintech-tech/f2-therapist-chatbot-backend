"""
Diagnostic script to test API connectivity and quota status
"""

import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

print("=" * 80)
print("GEMINI API DIAGNOSTIC")
print("=" * 80)

# Check API key
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    print(f"\n✓ GEMINI_API_KEY found")
    print(f"  Key length: {len(api_key)} characters")
    print(f"  Preview: {api_key[:20]}...{api_key[-10:]}")
else:
    print("\n✗ GEMINI_API_KEY not found!")
    exit(1)

# Initialize client
client = genai.Client(api_key=api_key)
print(f"\n✓ Gemini client initialized")

# Test 1: List available models
print("\n" + "=" * 80)
print("TEST 1: Available Models")
print("=" * 80)

try:
    models = client.models.list()
    print(f"\n✓ Successfully retrieved model list")
    print(f"\nAvailable models:")
    for model in models:
        print(f"  - {model.name}")
except Exception as e:
    print(f"\n✗ Error listing models: {e}")

# Test 2: Test embedding endpoint
print("\n" + "=" * 80)
print("TEST 2: Embedding API Call")
print("=" * 80)

try:
    print("\nAttempting to embed with 'text-embedding-2'...")
    result = client.models.embed_content(
        model="text-embedding-2",
        contents="Test query",
    )
    print(f"✓ text-embedding-2 works!")
    print(f"  Embedding dimension: {len(result.embeddings[0].values)}")
except Exception as e:
    print(f"✗ text-embedding-2 failed: {e}")

try:
    print("\nAttempting to embed with 'gemini-embedding-2'...")
    result = client.models.embed_content(
        model="gemini-embedding-2",
        contents="Test query",
    )
    print(f"✓ gemini-embedding-2 works!")
    print(f"  Embedding dimension: {len(result.embeddings[0].values)}")
except Exception as e:
    print(f"✗ gemini-embedding-2 failed: {e}")

# Test 3: Test generation endpoint (simple)
print("\n" + "=" * 80)
print("TEST 3: Generation API Call")
print("=" * 80)

try:
    print("\nAttempting generation with 'gemini-3-flash-preview'...")
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents="Say 'Hello' only",
    )
    print(f"✓ gemini-3-flash-preview works!")
    print(f"  Response: {response.text}")
except Exception as e:
    error_str = str(e)
    print(f"✗ gemini-3-flash-preview failed: {e}")

    # Check if it's a quota or rate-limit error
    lowered = error_str.lower()
    if "exceeded your current quota" in lowered or "daily limit" in lowered:
        print("\n  🔴 QUOTA EXHAUSTED - You've hit a usage limit")
        print("     This is a real quota issue")
    elif "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
        print("\n  🟠 RATE LIMITED OR RESOURCE_EXHAUSTED")
        print("     This does not necessarily mean your daily quota is exhausted")
    elif "404" in error_str or "NOT_FOUND" in error_str:
        print("\n  🟡 MODEL NOT FOUND - Check model name")
    else:
        print("\n  🟠 UNKNOWN ERROR")

print("\n" + "=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
