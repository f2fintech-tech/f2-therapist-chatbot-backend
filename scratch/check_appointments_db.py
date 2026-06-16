import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from src.models import engine, AdvisorAppointment

def check():
    with Session(engine) as session:
        appts = session.query(AdvisorAppointment).all()
        print(f"Total appointments: {len(appts)}")
        for a in appts:
            print(f"ID: {a.id} | Advisor: {a.advisor_name} (ID: {a.advisor_id}) | Completed: {a.completed} | Rating: {a.rating} | Feedback: {a.feedback}")

if __name__ == "__main__":
    check()
