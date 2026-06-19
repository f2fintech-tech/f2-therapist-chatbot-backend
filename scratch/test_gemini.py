import os
from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

print("Initializing ChatGoogleGenerativeAI...")
api_key = os.getenv("GEMINI_API_KEY")
llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    temperature=0.7,
    max_output_tokens=3072,
    google_api_key=api_key
)

print("Sending message to ChatGoogleGenerativeAI...")
try:
    response = llm.invoke([HumanMessage(content="hi")])
    print("Success! Response:")
    print(response.content)
except Exception as e:
    print("Error invoking LLM:", e)
