import bcrypt
from src.models import SessionLocal, Advisor

db = SessionLocal()
adv = db.query(Advisor).filter(Advisor.f2_fintech_id == 'F2-369-001').first()
if not adv or not adv.password_hash:
    print("Advisor not found or no password hash")
else:
    hash_val = adv.password_hash.encode()
    print("Hash in DB:", adv.password_hash)
    passwords = [
        'FinHeal@123', 'FinHeal', 'password', 'password123', '123456', 
        'F2fintech_26', 'RajKumari', 'rajkumari', 'RajKumari@123', 
        'F2-369-001', 'f2-369-001', 'Harpreet', 'harpreet', 'Harpreet@123',
        'Sales Manager', 'sales manager', 'SalesManager', 'salesmanager',
        'Harpreet001', 'harpreet001'
    ]

    found = False
    for pw in passwords:
        if bcrypt.checkpw(pw.encode(), hash_val):
            print(f"Match found: '{pw}'")
            found = True
            break

    if not found:
        print("No match found in standard list")
db.close()
