import os
from sqlalchemy import inspect, text
from src.models import engine

def inspect_db():
    inspector = inspect(engine)
    try:
        tables = inspector.get_table_names()
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        return

    print("=== Tables in Database ===")
    for idx, name in enumerate(tables, 1):
        print(f"{idx}. {name}")
    print("\n" + "="*50 + "\n")

    # Dump rows of each table
    with engine.connect() as conn:
        for table_name in tables:
            print(f"=== Table: {table_name} (First 10 rows) ===")
            try:
                columns = [col["name"] for col in inspector.get_columns(table_name)]
                result = conn.execute(text(f"SELECT * FROM {table_name} LIMIT 10;"))
                rows = result.fetchall()
                if not rows:
                    print("[Table is empty]")
                else:
                    print(" | ".join(columns))
                    print("-" * (len(" | ".join(columns))))
                    for row in rows:
                        try:
                            # Convert values to strings safely
                            row_vals = [str(val) if val is not None else "NULL" for val in row]
                            print(" | ".join(row_vals))
                        except UnicodeEncodeError:
                            row_vals = [str(val).encode('ascii', errors='replace').decode('ascii') if val is not None else "NULL" for val in row]
                            print(" | ".join(row_vals))
            except Exception as e:
                print(f"Error reading table {table_name}: {e}")
            print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    inspect_db()
