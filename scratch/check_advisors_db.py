import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from src.models import engine, Advisor, AdvisorAppointment

def check():
    with Session(engine) as session:
        advisors = session.query(Advisor).all()
        print(f"Total advisors: {len(advisors)}")
        for a in advisors:
            print(f"ID: {a.f2_fintech_id} | Name: {a.name} | Rating: {a.rating} | Reviews: {a.reviews_count} | Category: {a.category}")

if __name__ == "__main__":
    check()
