import os
import time
import json
from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.routers.chat import get_financial_therapy_prompt, get_finetuned_system_prompt

api_key = os.getenv("GEMINI_API_KEY")
system_prompt = get_finetuned_system_prompt()
user_message = "**User's Question:**\nhi, I need help budgeting"

models = ["gemini-2.5-flash", "gemini-3-flash-preview"]

for model_name in models:
    print(f"\n--- Testing {model_name} on chat response JSON generation ---")
    try:
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.7,
            max_output_tokens=3072,
            google_api_key=api_key
        )
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        start = time.perf_counter()
        response = llm.invoke(messages)
        duration = time.perf_counter() - start
        
        print(f"Time taken: {duration:.2f}s")
        print(f"Raw Response: {response.content}")
        
        # Try parsing
        content = response.content
        if isinstance(content, list):
            print("WARNING: Content is a list!")
            content = str(content)
        try:
            parsed = json.loads(content)
            print("Successfully parsed JSON!")
            print(f"Parsed response keys: {list(parsed.keys())}")
            print(f"Response preview: {parsed.get('response')}")
        except Exception as pe:
            print(f"Failed to parse JSON: {pe}")
            
    except Exception as e:
        print(f"Error: {e}")
