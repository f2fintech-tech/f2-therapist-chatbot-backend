import sqlite3
import os

def inspect():
    # Connect to SQLite database relative to the script's directory
    db_path = os.path.join(os.path.dirname(__file__), 'test.db')
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Get list of all tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cur.fetchall()]
    print("=== Tables in test.db ===")
    for idx, name in enumerate(tables, 1):
        print(f"{idx}. {name}")
    print("\n" + "="*50 + "\n")

    # Dump rows of each table
    for table_name in tables:
        print(f"=== Table: {table_name} (First 10 rows) ===")
        try:
            cur.execute(f"PRAGMA table_info({table_name})")
            cols = [col[1] for col in cur.fetchall()]
            cur.execute(f"SELECT * FROM {table_name} LIMIT 10;")
            rows = cur.fetchall()
            if not rows:
                print("[Table is empty]")
            else:
                print(" | ".join(cols))
                print("-" * (len(" | ".join(cols))))
                for row in rows:
                    try:
                        print(" | ".join(str(val) for val in row))
                    except UnicodeEncodeError:
                        print(" | ".join(str(val).encode('ascii', errors='replace').decode('ascii') for val in row))
        except Exception as e:
            print(f"Error reading table {table_name}: {e}")
        print("\n" + "="*50 + "\n")

    conn.close()

if __name__ == "__main__":
    inspect()
