import sys
from sqlalchemy import text
from src.models import engine

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_query.py \"YOUR SQL QUERY\"")
        print("Example: python run_query.py \"SELECT * FROM users LIMIT 5;\"")
        sys.exit(1)
        
    query_str = sys.argv[1]
    print(f"Executing Query: {query_str}")
    print("-" * 60)
    
    try:
        # Open connection and execute
        with engine.connect() as connection:
            result = connection.execute(text(query_str))
            
            # If the query returns rows (e.g. SELECT)
            if result.returns_rows:
                rows = result.fetchall()
                if not rows:
                    print("[No rows returned]")
                    return
                
                # Fetch headers
                keys = list(result.keys())
                # Calculate column widths for pretty formatting
                col_widths = {key: len(str(key)) for key in keys}
                for row in rows:
                    for key, val in zip(keys, row):
                        col_widths[key] = max(col_widths[key], len(str(val)))
                
                # Print headers
                header_line = " | ".join(f"{str(key):<{col_widths[key]}}" for key in keys)
                print(header_line)
                print("-" * len(header_line))
                
                # Print rows
                for row in rows:
                    row_line = " | ".join(f"{str(val):<{col_widths[key]}}" for key, val in zip(keys, row))
                    print(row_line)
                
                print("-" * len(header_line))
                print(f"Total rows returned: {len(rows)}")
            else:
                # If transaction is successful (for DDL or DML statements like INSERT, UPDATE, DELETE, CREATE, DROP)
                # Note: engine.begin() or connection.commit() is needed to commit changes.
                # In SQLAlchemy 2.0, connections do not auto-commit. We need to commit the transaction.
                # Let's run with a transaction:
                pass
    except Exception as e:
        print(f"[ERROR] Query failed: {e}")

if __name__ == "__main__":
    # Let's adjust the transaction block for proper SQLAlchemy 2.0 auto-commit / commit
    # We will use engine.begin() so it commits automatically on success, and rollbacks on exception.
    try:
        if len(sys.argv) < 2:
            print("Usage: python run_query.py \"YOUR SQL QUERY\"")
            print("Example: python run_query.py \"SELECT * FROM users LIMIT 5;\"")
            sys.exit(1)
            
        query_str = sys.argv[1]
        print(f"Executing Query: {query_str}")
        print("-" * 60)
        
        with engine.begin() as connection:
            result = connection.execute(text(query_str))
            
            if result.returns_rows:
                rows = result.fetchall()
                if not rows:
                    print("[No rows returned]")
                else:
                    keys = list(result.keys())
                    col_widths = {key: len(str(key)) for key in keys}
                    for row in rows:
                        for key, val in zip(keys, row):
                            col_widths[key] = max(col_widths[key], len(str(val)))
                    
                    header_line = " | ".join(f"{str(key):<{col_widths[key]}}" for key in keys)
                    print(header_line)
                    print("-" * len(header_line))
                    for row in rows:
                        row_line = " | ".join(f"{str(val):<{col_widths[key]}}" for key, val in zip(keys, row))
                        try:
                            print(row_line)
                        except UnicodeEncodeError:
                            # Fallback if the terminal doesn't support the characters (like emojis)
                            print(row_line.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8'))
                    print("-" * len(header_line))
                    print(f"Total rows returned: {len(rows)}")
            else:
                print("Query executed successfully. Changes committed.")
                print(f"Rows affected: {result.rowcount}")
                
    except Exception as e:
        print(f"[ERROR] Query failed: {e}")
