import os
import sys

backend_dir = r"d:\FinHeal-Friend\f2-therapist-chatbot-backend"
sys.path.append(backend_dir)

from src.models import SessionLocal, Advisor

db = SessionLocal()
try:
    advisors = db.query(Advisor).all()
    print("=" * 60)
    print("ALL ADVISORS IN DATABASE")
    print("=" * 60)
    for a in advisors:
        print(f"ID: {a.f2_fintech_id}")
        print(f"Name: {a.name}")
        print(f"Designation: {a.designation}")
        print(f"Availability: {a.availability}")
        print(f"Next Slot: {a.next_slot}")
        print("-" * 60)
finally:
    db.close()
