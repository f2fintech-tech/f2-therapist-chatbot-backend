import sys
sys.path.insert(0, '.')

from src.models import get_db, AdvisorAppointment, User

def show_appointments():
    db = next(get_db())
    try:
        results = db.query(
            AdvisorAppointment.id,
            AdvisorAppointment.advisor_name,
            User.email.label("client_email"),
            AdvisorAppointment.date,
            AdvisorAppointment.time,
            AdvisorAppointment.cancelled,
            AdvisorAppointment.feedback
        ).outerjoin(User, AdvisorAppointment.user_id == User.id).order_by(AdvisorAppointment.booked_at.desc()).all()
        
        if not results:
            print("\nNo appointments found in the database.\n")
            return
            
        print(f"\nFound {len(results)} appointments:\n")
        
        headers = ["ID", "Advisor Name", "Client Email", "Date", "Time", "Cancelled", "Cancellation Reason / Feedback"]
        # Format rows
        rows = []
        for r in results:
            rows.append([
                r.id or "",
                r.advisor_name or "",
                r.client_email or "Guest/None",
                r.date or "",
                r.time or "",
                "Yes" if r.cancelled else "No",
                r.feedback or ""
            ])
            
        # Determine column widths
        widths = [len(h) for h in headers]
        for row in rows:
            for i, val in enumerate(row):
                widths[i] = max(widths[i], len(str(val)))
                
        # Print header
        header_str = " | ".join(f"{h:<{widths[i]}}" for i, h in enumerate(headers))
        print(header_str)
        print("-" * len(header_str))
        
        # Print rows
        for row in rows:
            print(" | ".join(f"{str(val):<{widths[i]}}" for i, val in enumerate(row)))
        print()
        
    except Exception as e:
        print(f"Error querying appointments: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    show_appointments()
