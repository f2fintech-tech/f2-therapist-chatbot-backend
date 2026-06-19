import os
import time
from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

models = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-3-flash-preview"]
api_key = os.getenv("GEMINI_API_KEY")

for model_name in models:
    print(f"\n--- Testing {model_name} ---")
    try:
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.7,
            google_api_key=api_key
        )
        
        # Test 1: Invoke (non-streaming)
        start = time.perf_counter()
        response = llm.invoke([HumanMessage(content="Hello, reply with exactly 'Hi there!'")])
        duration = time.perf_counter() - start
        print(f"Non-streaming duration: {duration:.2f}s")
        print(f"Response: {response.content}")
        
        # Test 2: Stream (measure first token time)
        start_stream = time.perf_counter()
        first_token_time = None
        chunks = []
        for chunk in llm.stream([HumanMessage(content="Hello, count from 1 to 5, spaced out.")]):
            if first_token_time is None:
                first_token_time = time.perf_counter() - start_stream
            chunks.append(chunk.content if hasattr(chunk, 'content') else str(chunk))
        
        total_stream_time = time.perf_counter() - start_stream
        print(f"Streaming: First token: {first_token_time:.2f}s, Total time: {total_stream_time:.2f}s")
        print(f"Stream output: {''.join(chunks)}")
    except Exception as e:
        print(f"Error with {model_name}: {e}")
