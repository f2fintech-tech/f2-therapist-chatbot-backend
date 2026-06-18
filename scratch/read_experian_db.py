import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load env variables
load_dotenv()

db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_username = os.getenv("DB_USERNAME")
db_password = os.getenv("DB_PASSWORD")
db_database = os.getenv("DB_DATABASE")

db_url = f"postgresql://{db_username}:{db_password}@{db_host}:{db_port}/{db_database}"

print("Connecting to database...")
engine = create_engine(db_url)

try:
    with engine.connect() as conn:
        print("Successfully connected!")
        
        # Query UserCreditReport
        query = text("SELECT id, user_id, bureau, score, report_data, raw_bureau_json, fetched_at FROM user_credit_reports ORDER BY fetched_at DESC LIMIT 5")
        result = conn.execute(query)
        
        rows = result.all()
        print(f"\nFound {len(rows)} total records.")
        for row in rows:
            print("-" * 80)
            print("ID:", row.id)
            print("User ID:", row.user_id)
            print("Bureau:", row.bureau)
            print("Score:", row.score)
            print("Fetched At:", row.fetched_at)
            print("Report Data:", str(row.report_data)[:500])
            print("Raw Bureau JSON:", str(row.raw_bureau_json)[:500])
except Exception as e:
    print("Error:", e)
