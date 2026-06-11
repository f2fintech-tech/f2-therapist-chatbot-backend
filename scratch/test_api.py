import sys
import os
import traceback

# Ensure the backend directory is in python path
sys.path.insert(0, os.path.abspath('.'))

try:
    from fastapi.testclient import TestClient
    from src.main import app

    client = TestClient(app)
    print("FastAPI app loaded successfully.")
    
    # Try request to root
    print("Sending request to '/'...")
    response = client.get("/")
    print("Root response:", response.status_code, response.json())

    # Try request to check health
    print("Sending request to '/health'...")
    response = client.get("/health")
    print("Health response:", response.status_code, response.json())

    # Try request to get conversations
    print("Sending request to '/api/v1/conversations'...")
    response = client.get("/api/v1/conversations")
    print("Conversations response:", response.status_code, response.json())

except Exception as e:
    print("ERROR OCCURRED:")
    traceback.print_exc()
