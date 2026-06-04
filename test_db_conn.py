import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect

# Load environment variables
load_dotenv()

def get_database_url():
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USERNAME")
    db_pass = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_DATABASE")

    if db_host and db_user and db_pass and db_name:
        return f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

    return os.getenv("DATABASE_URL")

def main():
    url = get_database_url()
    if not url:
        print("[ERROR] No database credentials found in environment or .env file.")
        return

    # Redact password for safe logging
    safe_url = url
    if "@" in url:
        parts = url.split("@")
        cred_parts = parts[0].split(":")
        if len(cred_parts) > 2:
            cred_parts[2] = "********"
            safe_url = ":".join(cred_parts) + "@" + parts[1]

    print(f"Connecting to: {safe_url}")
    try:
        engine = create_engine(url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print("\n[SUCCESS] Connected to PostgreSQL database successfully.")
        print(f"Tables found in database ({len(tables)}):")
        for table in tables:
            print(f"  - {table}")
    except Exception as e:
        print("\n[ERROR] Failed to connect to database:")
        print(str(e))

if __name__ == "__main__":
    main()
