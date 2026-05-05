import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore

def load_data_to_pinecone(file_path):
    print(f"Loading document: {file_path}")

    # 1. Load the Document
    loader = PyPDFLoader(file_path)
    documents = loader.load()

    # 2. Split the Document into chunks
    # We chunk it so we don't overwhelm the AI with a massive wall of text later
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100 # A little overlap keeps sentences from breaking awkwardly
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Split into {len(chunks)} chunks.")

    # 3. Setup Embeddings
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2")

    # 4. Upload to Pinecone!
    index_name = "f2-therapy-index"

    print("Uploading to Pinecone... this might take a minute.")
    # This automatically embeds the text and uploads it to your index
    PineconeVectorStore.from_documents(
        chunks,
        embeddings,
        index_name=index_name
    )
    print("Upload complete! The chatbot is now smarter.")

if __name__ == "__main__":
    # You will run this file and point it to your actual financial data
    # Example: load_data_to_pinecone("data/financial_guidelines.pdf")
    pass
