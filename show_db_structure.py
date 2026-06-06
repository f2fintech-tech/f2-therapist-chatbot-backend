import sys
sys.path.insert(0, '.')
from src.models import engine, get_db, UserCreditReport, UserConsolidatedProfile
from sqlalchemy import inspect

insp = inspect(engine)
tables = insp.get_table_names()

print("=" * 60)
print("ALL TABLES IN YOUR POSTGRESQL DATABASE")
print("=" * 60)

for t in tables:
    cols = insp.get_columns(t)
    json_cols = [c['name'] for c in cols if 'json' in str(c['type']).lower() or 'json' in c['name'].lower()]
    has_json = " [HAS JSON COLUMNS]" if json_cols else ""
    print(f"\n  TABLE: {t}{has_json}")
    for c in cols:
        marker = " <-- JSON" if c['name'] in json_cols else ""
        print(f"    {c['name']:40} {str(c['type']):20}{marker}")

print("\n")
print("=" * 60)
print("WHERE CIBIL REPORT DATA IS STORED")
print("=" * 60)

db = next(get_db())

# 1. user_credit_reports table
print("\n[1] TABLE: user_credit_reports")
print("    Stores one row per CIBIL fetch. Columns that hold JSON:")
print("    - report_data      : Normalized (parsed) report returned to frontend")
print("    - raw_bureau_json  : Raw JSON from CIBIL API — used to re-parse accurately")

rpt = db.query(UserCreditReport).order_by(UserCreditReport.fetched_at.desc()).first()
if rpt:
    has_raw = rpt.raw_bureau_json is not None
    accs = rpt.report_data.get("accounts", []) if rpt.report_data else []
    open_accs = [a for a in accs if a.get("is_active")]
    print(f"\n    Latest row:")
    print(f"      score           = {rpt.score}")
    print(f"      bureau          = {rpt.bureau}")
    print(f"      fetched_at      = {rpt.fetched_at}")
    print(f"      has raw JSON?   = {has_raw}")
    print(f"      accounts stored = {len(accs)} total, {len(open_accs)} open")
    raw_keys = list(rpt.raw_bureau_json.keys()) if has_raw else []
    print(f"      raw JSON keys   = {raw_keys}")

# 2. user_consolidated_profiles table
print("\n[2] TABLE: user_consolidated_profiles")
print("    Stores everything about a user as one big JSON blob in the 'data' column.")
print("    cibil_report is stored under:  data['cibil_report']")

cp = db.query(UserConsolidatedProfile).first()
if cp and cp.data:
    top_keys = list(cp.data.keys())
    print(f"\n    Top-level keys in data: {top_keys}")
    if "cibil_report" in cp.data:
        cr = cp.data["cibil_report"]
        print(f"    data['cibil_report'] keys: {list(cr.keys())}")
        accs2 = cr.get("accounts", [])
        open2 = [a for a in accs2 if a.get("is_active")]
        print(f"    accounts: {len(accs2)} total, {len(open2)} open")

db.close()

print("\n")
print("=" * 60)
print("SUMMARY: Which table to check?")
print("=" * 60)
print("""
  For CIBIL raw API data (source of truth):
    TABLE  : user_credit_reports
    COLUMN : raw_bureau_json

  For normalized/parsed report (what frontend sees):
    TABLE  : user_credit_reports
    COLUMN : report_data

  For user's latest cached report (also used by frontend):
    TABLE  : user_consolidated_profiles
    COLUMN : data  (access as data->>'cibil_report' in SQL)

  SQL to inspect directly:
    SELECT id, score, fetched_at,
           report_data->>'score' AS parsed_score,
           raw_bureau_json IS NOT NULL AS has_raw
    FROM user_credit_reports
    ORDER BY fetched_at DESC;
""")
