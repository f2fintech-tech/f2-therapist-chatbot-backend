import sqlite3
import os
from dotenv import load_dotenv
from sqlalchemy import text
from src.models import (
    engine, User, Conversation, ConversationMessage,
    TestResult, MoodLiveState, MoodTrendState, WellnessBreakdown,
    UserConsolidatedProfile
)
from sqlalchemy.orm import sessionmaker

# Load env variables first
load_dotenv()

def migrate():
    # SQLite connection
    sqlite_db_path = os.path.join(os.path.dirname(__file__), 'test.db')
    if not os.path.exists(sqlite_db_path):
        print(f"[ERROR] SQLite database file not found at: {sqlite_db_path}")
        return

    print(f"Connecting to SQLite database: {sqlite_db_path}")
    sqlite_conn = sqlite3.connect(sqlite_db_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    # PostgreSQL Session
    SessionPostgres = sessionmaker(bind=engine)
    pg_session = SessionPostgres()

    print("Connecting to PostgreSQL database...")
    try:
        # Test postgres connection
        pg_session.execute(text("SELECT 1"))
    except Exception as e:
        print(f"[ERROR] Failed to connect to PostgreSQL: {e}")
        sqlite_conn.close()
        return

    # Tables to migrate in order of dependencies (parent tables first)
    tables = [
        ("users", User),
        ("conversations", Conversation),
        ("conversation_messages", ConversationMessage),
        ("mood_live_state", MoodLiveState),
        ("mood_trend_state", MoodTrendState),
        ("test_results", TestResult),
        ("wellness_breakdown", WellnessBreakdown),
        ("user_consolidated_profiles", UserConsolidatedProfile),
    ]

    for table_name, model_class in tables:
        print(f"\n--- Migrating table: {table_name} ---")
        try:
            sqlite_cur.execute(f"SELECT * FROM {table_name}")
            rows = sqlite_cur.fetchall()
            if not rows:
                print(f"No records found in SQLite table '{table_name}'. Skipping.")
                continue

            print(f"Found {len(rows)} records in SQLite. Migrating...")
            
            # Retrieve column definitions for the SQLAlchemy model
            columns = [c.name for c in model_class.__table__.columns]
            
            migrated_count = 0
            for row in rows:
                # Convert sqlite row to dict matching model columns
                row_dict = dict(row)
                
                # Check for columns present in SQLite but not in PostgreSQL schema
                filtered_dict = {}
                for col in columns:
                    if col in row_dict:
                        filtered_dict[col] = row_dict[col]

                # Handlers for datetime strings (sqlite stores datetime as string)
                for key, val in filtered_dict.items():
                    if val is not None and ('_at' in key or key == 'completed_at' or key == 'created_at' or key == 'updated_at'):
                        from datetime import datetime
                        try:
                            # SQLite might store as "YYYY-MM-DD HH:MM:SS.ffffff" or "YYYY-MM-DD HH:MM:SS"
                            if isinstance(val, str):
                                val_clean = val.split('+')[0] # remove timezone offset if any
                                if '.' in val_clean:
                                    filtered_dict[key] = datetime.strptime(val_clean, "%Y-%m-%d %H:%M:%S.%f")
                                else:
                                    filtered_dict[key] = datetime.strptime(val_clean, "%Y-%m-%d %H:%M:%S")
                        except Exception:
                            # fallback to raw if parsing fails
                            pass
                    
                    # Convert JSON fields
                    if val is not None and model_class.__table__.columns[key].type.__class__.__name__ == 'JSON':
                        import json
                        if isinstance(val, str):
                            try:
                                filtered_dict[key] = json.loads(val)
                            except Exception:
                                pass

                # Check if record already exists in Postgres (by PK)
                pk_names = [key.name for key in model_class.__table__.primary_key.columns]
                
                # Build filter query for primary keys
                query = pg_session.query(model_class)
                for pk in pk_names:
                    query = query.filter(getattr(model_class, pk) == filtered_dict[pk])
                
                exists = query.first()
                if exists:
                    # Update existing record
                    for k, v in filtered_dict.items():
                        setattr(exists, k, v)
                else:
                    # Insert new record
                    new_record = model_class(**filtered_dict)
                    pg_session.add(new_record)
                
                migrated_count += 1

            pg_session.commit()
            print(f"Successfully migrated/merged {migrated_count} records to PostgreSQL '{table_name}'.")

        except Exception as e:
            pg_session.rollback()
            print(f"[ERROR] Failed to migrate table '{table_name}': {e}")

    sqlite_conn.close()
    pg_session.close()
    print("\n================ Migration Complete ================ ")

if __name__ == "__main__":
    migrate()
