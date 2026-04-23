import os
from google import genai
from pinecone import Pinecone

# 1. Setup Gemini and Pinecone
# The new genai.Client() automatically looks for the GEMINI_API_KEY environment variable!
client = genai.Client() 
pc = Pinecone(api_key=os.getenv("export PINECONE_API_KEY="pcsk_66p3nV_DsKrE4Kx7we6oC6P6jgiYb6djJFJSDzAVtfhyCWsPUWweXA3FrWNBZbDenzeyb2""))
index = pc.Index("f2-therapy-index")

def get_financial_therapy(user_message):
    # STEP 1: Turn user message into 768 numbers (Embedding)
    # Updated for the new SDK syntax
    embed_result = client.models.embed_content(
        model="text-embedding-004",
        contents=user_message,
    )
    # Extract the vector from the new response structure
    user_vector = embed_result.embeddings[0].values

    # STEP 2: Find the 'vibe' in Pinecone
    search_results = index.query(
        vector=user_vector, 
        top_k=2, 
        include_metadata=True
    )
    
    # Get the therapeutic text we stored in the metadata
    # (Using a safe fallback just in case the metadata is empty)
    context_text = ""
    if search_results['matches']:
        context_text = search_results['matches'][0].get('metadata', {}).get('text', '')

    # STEP 3: Give context to Gemini 3.1 to generate the therapy
    prompt = f"""
    You are a Financial Therapist for F2 Fintech. 
    Role: Relax the customer. You are NOT an authorized advisor.
    Use this guide: {context_text}
    User says: {user_message}
    """
    
    # Updated for the new SDK generation syntax
    response = client.models.generate_content(
        model='gemini-3.1-flash',
        contents=prompt,
    )
    
    return response.text