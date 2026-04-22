import os
import google.generativeai as genai
from pinecone import Pinecone

# 1. Setup Gemini and Pinecone
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("f2-therapy-index")

def get_financial_therapy(user_message):
    # STEP 1: Turn user message into 768 numbers (Embedding)
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=user_message,
        task_type="retrieval_query"
    )
    user_vector = result['embedding']

    # STEP 2: Find the 'vibe' in Pinecone
    search_results = index.query(
        vector=user_vector, 
        top_k=2, 
        include_metadata=True
    )
    
    # Get the therapeutic text we stored in the metadata
    context_text = search_results['matches'][0]['metadata']['text']

    # STEP 3: Give context to Gemini 3.1 to generate the therapy
    model = genai.GenerativeModel('gemini-3.1-pro')
    prompt = f"""
    You are a Financial Therapist for F2 Fintech. 
    Role: Relax the customer. You are NOT an authorized advisor.
    Use this guide: {context_text}
    User says: {user_message}
    """
    
    response = model.generate_content(prompt)
    return response.text