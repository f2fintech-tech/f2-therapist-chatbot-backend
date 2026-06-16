from src.models import SessionLocal, Advisor, AdvisorAppointment

def reset_db():
    db = SessionLocal()
    try:
        # Delete all completed advisor appointments to clear review comments
        deleted_count = db.query(AdvisorAppointment).delete()
        print(f"Deleted {deleted_count} appointments/reviews from database.")
        
        # Reset all advisors' ratings and review counts to 0.0 and 0
        advisors = db.query(Advisor).all()
        for a in advisors:
            a.rating = 0.0
            a.reviews_count = 0
        db.commit()
        print(f"Successfully reset ratings and review counts for {len(advisors)} advisors to 0.0/0.")
    except Exception as e:
        db.rollback()
        print(f"Error resetting database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_db()
