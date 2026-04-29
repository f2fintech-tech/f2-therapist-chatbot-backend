import os
from google import genai
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

# Load keys
load_dotenv()

def setup_and_seed_pinecone():
    # 1. Setup New 2026 Clients
    # The new SDK uses a Client object
    google_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    
    index_name = "f2-therapy-index"

    # 2. Create Index if it doesn't exist
    if index_name not in [idx.name for idx in pc.list_indexes()]:
        pc.create_index(
            name=index_name,
            dimension=768, 
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )

    index = pc.Index(index_name)

    # 3. Therapy Data
    therapy_data = [
        {"id": "advice_01", "text": "Money stress is heavy, but you are not alone. Take a deep breath."},
        {"id": "advice_02", "text": "Missing a payment is a hurdle, not a wall. Let's look at aggregator options."}
    ]

    # 4. Use the new 'embed_content' method
    for item in therapy_data:
        result = google_client.models.embed_content(
            model="gemini-embedding-2",
            contents=item["text"]
        )
        
        # In the new SDK, embeddings are accessed like this:
        embedding_values = result.embeddings[0].values

        index.upsert(vectors=[{
            "id": item["id"],
            "values": embedding_values,
            "metadata": {"text": item["text"]}
        }])

    print("✅ Success! Your 2026 Pinecone library is ready.")

if __name__ == "__main__":
    setup_and_seed_pinecone()