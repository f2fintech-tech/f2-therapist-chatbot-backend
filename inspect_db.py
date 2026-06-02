import sqlite3
import pandas as pd

def inspect():
    # Connect to SQLite database
    conn = sqlite3.connect('test.db')

    # Get list of all tables
    tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
    print("=== Tables in test.db ===")
    for idx, name in enumerate(tables['name'], 1):
        print(f"{idx}. {name}")
    print("\n" + "="*50 + "\n")

    # Dump rows of each table
    for table_name in tables['name']:
        print(f"=== Table: {table_name} (First 10 rows) ===")
        try:
            df = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT 10;", conn)
            if df.empty:
                print("[Table is empty]")
            else:
                print(df.to_string(index=False))
        except Exception as e:
            print(f"Error reading table {table_name}: {e}")
        print("\n" + "="*50 + "\n")

    conn.close()

if __name__ == "__main__":
    inspect()
