import os
import time
from dotenv import load_dotenv
load_dotenv()

from src.knowledge.retriever import get_relevant_context
print("Querying context for: 'hi, I need help budgeting'...")
start = time.perf_counter()
try:
    ctx = get_relevant_context("hi, I need help budgeting")
    print(f"Completed in {time.perf_counter() - start:.2f}s")
    print("Retrieved docs count:", len(ctx))
    for doc in ctx:
        print(f"- [Score: {doc['score']:.2f}] {doc['content'][:150]}...")
except Exception as e:
    print("Error:", e)
