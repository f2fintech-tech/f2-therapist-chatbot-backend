import os
import google.generativeai as genai
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

# Load your secret keys from .env
load_dotenv()

def setup_and_seed_pinecone():
    # 1. Setup Clients
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    
    index_name = "f2-therapy-index"

    # 2. Create Index if it doesn't exist
    if index_name not in pc.list_indexes().names():
        pc.create_index(
            name=index_name,
            dimension=768, # Correct for Gemini
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )

    index = pc.Index(index_name)

    # 3. Example Therapy Scripts to feed the 'Librarian'
    # In a real scenario, you would load these from a text file or PDF
    therapy_data = [
        {
            "id": "advice_01",
            "text": "When feeling overwhelmed by EMI dates, take a 5-minute breathing exercise. Financial stress is common, and you are not alone."
        },
        {
            "id": "advice_02",
            "text": "Missing a payment doesn't define your worth. F2 Fintech suggests looking into consolidation if you have multiple high-interest debts."
        }
    ]

    # 4. Turn text into 768 numbers and upload
    for item in therapy_data:
        # Convert text to Vector
        embedding = genai.embed_content(
            model="models/text-embedding-004",
            content=item["text"],
            task_type="retrieval_document"
        )["embedding"]

        # Upload to Pinecone (Upsert)
        index.upsert(vectors=[{
            "id": item["id"],
            "values": embedding,
            "metadata": {"text": item["text"]} # Crucial for the bot to read later!
        }])

    print("Success! Your Pinecone filing cabinet is now filled.")

if __name__ == "__main__":
    setup_and_seed_pinecone()