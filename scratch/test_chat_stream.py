import httpx
import json
import time

url = "http://localhost:8000/api/v1/chat/"
payload = {
    "message": "hi, I need help budgeting",
    "user_id": "d4fe7aa6-3bca-422d-b5e3-6feacc6bbc10"
}
headers = {
    "Authorization": "Bearer dev_api_key"
}

print(f"Sending POST to {url}...")
start_time = time.perf_counter()

try:
    with httpx.stream("POST", url, json=payload, headers=headers, timeout=60) as r:
        print(f"Response status: {r.status_code}")
        print(f"Time to headers: {time.perf_counter() - start_time:.2f}s")
        
        last_time = time.perf_counter()
        for line in r.iter_lines():
            if line.strip():
                now = time.perf_counter()
                delta = now - last_time
                last_time = now
                print(f"[+{delta:.2f}s] Chunk: {line}")
except Exception as e:
    print(f"Error during streaming: {type(e).__name__}: {e}")
