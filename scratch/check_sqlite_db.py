import sqlite3
import os

def check_sqlite():
    db_path = r"d:\Finheal-friend\f2-therapist-chatbot-backend\test.db"
    if not os.path.exists(db_path):
        print("SQLite test.db does not exist")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"SQLite Tables: {tables}")
        
        if "advisors" in tables:
            cursor.execute("SELECT f2_fintech_id, name, rating, reviews_count, category FROM advisors;")
            rows = cursor.fetchall()
            print(f"Advisors in SQLite (Total: {len(rows)}):")
            for r in rows:
                print(f"ID: {r[0]} | Name: {r[1]} | Rating: {r[2]} | Reviews: {r[3]} | Category: {r[4]}")
        else:
            print("No advisors table in SQLite test.db")
    except Exception as e:
        print(f"Error querying SQLite: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_sqlite()
