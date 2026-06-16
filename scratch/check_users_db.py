import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from src.models import engine, User

def check():
    with Session(engine) as session:
        users = session.query(User).all()
        print(f"Total users: {len(users)}")
        for u in users:
            print(f"ID: {u.id} | Email: {u.email} | Name: {u.name}")

if __name__ == "__main__":
    check()
