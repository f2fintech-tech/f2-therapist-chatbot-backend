import sys
sys.path.insert(0, '.')
from src.models import get_db, UserCreditReport, UserConsolidatedProfile

db = next(get_db())

# Check most recent credit report 
rpt = db.query(UserCreditReport).order_by(UserCreditReport.fetched_at.desc()).first()
if rpt:
    data = rpt.report_data
    print('Report keys:', list(data.keys()) if isinstance(data, dict) else type(data))
    print('Has raw_cibil_json:', 'raw_cibil_json' in data if isinstance(data, dict) else 'N/A')
    print('Score:', data.get('score') if isinstance(data, dict) else 'N/A')
    accs = data.get('accounts', []) if isinstance(data, dict) else []
    print('Accounts count:', len(accs))
    for a in accs[:5]:
        print(' -', a.get('lender'), '|', a.get('type'), '| active:', a.get('is_active'))
else:
    print('No credit report in DB')

# Also check consolidated profile
cp = db.query(UserConsolidatedProfile).first()
if cp and cp.data and 'cibil_report' in cp.data:
    cr = cp.data['cibil_report']
    print('\nConsolidated profile cibil_report keys:', list(cr.keys()) if isinstance(cr, dict) else type(cr))
    print('Has raw_cibil_json in profile:', 'raw_cibil_json' in cr if isinstance(cr, dict) else 'N/A')
else:
    print('No cibil_report in consolidated profile')

db.close()
