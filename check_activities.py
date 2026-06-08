import sys
import json
sys.path.insert(0, '.')
from src.models import get_db, UserLoanCalculatorActivity, User

db = next(get_db())

try:
    results = db.query(UserLoanCalculatorActivity, User).join(
        User, UserLoanCalculatorActivity.user_id == User.id
    ).order_by(UserLoanCalculatorActivity.created_at.desc()).limit(10).all()

    if not results:
        print("No loan calculator activities found in database.")
    else:
        print(f"Found {len(results)} calculator activities:")
        print("=" * 80)
        for idx, (activity, user) in enumerate(results, 1):
            print(f"Activity #{idx}:")
            print(f"  User ID:         {activity.user_id}")
            print(f"  User Name:       {user.name}")
            print(f"  User Email:      {user.email}")
            print(f"  User Phone:      {user.phone}")
            print(f"  Calculator:      {activity.calculator_type}")
            print(f"  Loan Type:       {activity.loan_type}")
            print(f"  Created At:      {activity.created_at}")
            print(f"  Inputs:")
            try:
                print(json.dumps(activity.inputs, indent=4))
            except Exception:
                print(f"    {activity.inputs}")
            print("=" * 80)
finally:
    db.close()
