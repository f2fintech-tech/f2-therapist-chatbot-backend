import sys
sys.path.insert(0, '.')
from src.models import get_db, UserCreditReport, UserConsolidatedProfile
from src.utils.cibil_client import normalize_cibil_report_from_raw
from sqlalchemy.orm.attributes import flag_modified
import json, os

db = next(get_db())

# Get all users with credit reports but no raw_bureau_json
rows = db.query(UserCreditReport).all()
print(f"Total credit report rows: {len(rows)}")

for row in rows:
    print(f"\nUser: {row.user_id} | Bureau: {row.bureau} | Score: {row.score} | Has raw: {row.raw_bureau_json is not None}")

# Try to backfill from file
raw_file = "_last_cibil_raw_response.json"
if not os.path.exists(raw_file):
    print(f"\nNo {raw_file} found")
    db.close()
    exit()

with open(raw_file) as f:
    raw_data = json.load(f)

print(f"\n{raw_file} loaded, top-level keys: {list(raw_data.keys())}")

# Backfill for all users that have no raw_bureau_json
backfilled = 0
for row in rows:
    if row.raw_bureau_json is None:
        stored_report = row.report_data or {}
        row.raw_bureau_json = raw_data
        flag_modified(row, "raw_bureau_json")
        
        reparsed = normalize_cibil_report_from_raw(
            raw_data,
            name=stored_report.get("name", ""),
            phone=stored_report.get("phone", ""),
            pan=stored_report.get("pan", "")
        )
        
        if reparsed:
            if not reparsed.get("pdf_url") and stored_report.get("pdf_url"):
                reparsed["pdf_url"] = stored_report["pdf_url"]
            row.report_data = reparsed
            row.score = reparsed.get("score", row.score)
            flag_modified(row, "report_data")
            
            # Update consolidated profile
            profile = db.query(UserConsolidatedProfile).filter(UserConsolidatedProfile.user_id == row.user_id).first()
            if profile and profile.data:
                profile_data = dict(profile.data)
                profile_data["cibil_report"] = reparsed
                profile.data = profile_data
                flag_modified(profile, "data")
            
            open_accs = [a for a in reparsed.get("accounts", []) if a.get("is_active")]
            print(f"\n  Backfilled user {row.user_id}: {len(open_accs)} open accounts")
            for a in open_accs[:5]:
                print(f"    - {a['lender']} | {a['type']} | active: {a['is_active']}")
        
        backfilled += 1

db.commit()
print(f"\nBackfilled {backfilled} record(s)")
db.close()
