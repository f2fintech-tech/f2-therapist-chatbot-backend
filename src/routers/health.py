from fastapi import APIRouter
from pydantic import BaseModel
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Health"])

# ==================== Models ====================
class HealthCheckResponse(BaseModel):
    """Health check response model."""
    status: str
    version: str
    service: str
    database_configured: bool
    gemini_api_configured: bool
    pinecone_configured: bool
    aws_configured: bool

class StatusResponse(BaseModel):
    """Service status response model."""
    service: str
    status: str
    version: str
    environment: str

# ==================== Routes ====================
@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    Health check endpoint.

    Returns status of the service and configuration.
    """
    return HealthCheckResponse(
        status="healthy",
        version="0.1.0",
        service="Financial Therapist Chatbot Backend",
        database_configured=bool(os.getenv("DATABASE_URL") or (os.getenv("DB_HOST") and os.getenv("DB_USERNAME") and os.getenv("DB_PASSWORD") and os.getenv("DB_DATABASE"))),
        gemini_api_configured=bool(os.getenv("GEMINI_API_KEY")),
        pinecone_configured=bool(os.getenv("PINECONE_API_KEY")),
        aws_configured=bool(os.getenv("AWS_ACCESS_KEY_ID"))
    )

@router.get("/status", response_model=StatusResponse)
async def get_status():
    """
    Get service status and configuration info.

    Returns current service status and environment information.
    """
    return StatusResponse(
        service="Financial Therapist Chatbot",
        status="running",
        version="0.1.0",
        environment=os.getenv("ENVIRONMENT", "development")
    )

@router.get("/ready")
async def readiness_check():
    """
    Readiness check endpoint for Kubernetes or load balancers.

    Returns true if service is ready to accept requests.
    """
    return {
        "ready": True,
        "service": "Financial Therapist Chatbot Backend"
    }


# Temporary module-level diagnostic code to run on uvicorn reload
try:
    import zipfile
    import io
    import xml.etree.ElementTree as ET
    from src.utils.cam_generator import generate_cam_xlsx

    mock_accounts = [
        {"type": "Personal Loan", "lender": "SBI", "sanctioned_amount": 500000, "outstanding_balance": 450000, "emi": 12000, "open_date": "2025-08-20", "is_active": True},
        {"type": "Credit Card", "lender": "ICICI", "sanctioned_amount": 150000, "outstanding_balance": 45000, "emi": 3000, "open_date": "2026-01-01", "is_active": True},
        {"type": "Car Loan", "lender": "HDFC", "sanctioned_amount": 918998, "outstanding_balance": 540105, "emi": 19000, "open_date": "2025-01-10", "is_active": True},
        {"type": "Education Loan", "lender": "CANERA", "sanctioned_amount": 6750000, "outstanding_balance": 6650000, "emi": 0, "open_date": "2024-11-05", "is_active": True},
        {"type": "Business Loan", "lender": "HDFC", "sanctioned_amount": 285907, "outstanding_balance": 279991, "emi": 10000, "open_date": "2026-02-10", "is_active": True},
        {"type": "Home Loan", "lender": "CHOLA", "sanctioned_amount": 1519819, "outstanding_balance": 1519819, "emi": 40000, "open_date": "2026-03-12", "is_active": True},
        {"type": "Gold Loan", "lender": "AXIS", "sanctioned_amount": 200000, "outstanding_balance": 180000, "emi": 5000, "open_date": "2025-05-15", "is_active": True},
    ]

    report_data = {
        "score": 750,
        "band": "Excellent",
        "pan": "ABCDE1234F",
        "name": "Test CAM Customer",
        "phone": "9988775544",
        "metrics": {
            "payment_on_time_pct": 100,
            "credit_utilization_pct": 15,
            "credit_history_age_years": 4.5,
            "enquiries_l6m": 1,
            "secured_loans_count": 3,
            "unsecured_loans_count": 4,
            "write_offs": 0,
            "defaults": 0,
            "enquiries_l3m": 2,
            "enquiries_l3m_secured": 1,
            "enquiries_l3m_unsecured": 1
        },
        "accounts": mock_accounts,
        "tips": ["Keep up the good work!"],
        "pdf_url": "http://example.com/report.pdf",
        "fetched_at": "2026-06-15T12:00:00Z"
    }

    cam_bytes = generate_cam_xlsx(report_data, "test@example.com")

    output = []
    with zipfile.ZipFile(io.BytesIO(cam_bytes), 'r') as z:
        sheet_bytes = z.read('xl/worksheets/sheet1.xml')
        root = ET.fromstring(sheet_bytes)
        ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        
        sheet_data = root.find('ns:sheetData', ns)
        if sheet_data is not None:
            for row in sheet_data.findall('ns:row', ns):
                r_num = int(row.attrib.get('r', 1))
                row_cells = []
                for cell in row.findall('ns:c', ns):
                    ref = cell.attrib.get('r', '')
                    f_elem = cell.find('ns:f', ns)
                    v_elem = cell.find('ns:v', ns)
                    f_text = f_elem.text if f_elem is not None else ""
                    v_text = v_elem.text if v_elem is not None else ""
                    if f_text or v_text:
                        row_cells.append(f"{ref}: F='{f_text}', V='{v_text}'")
                if row_cells:
                    output.append(f"Row {r_num}: " + ", ".join(row_cells))

        try:
            t1_bytes = z.read('xl/tables/table1.xml')
            t1_root = ET.fromstring(t1_bytes)
            output.append("--- Table1 ---")
            output.append(f"Ref: {t1_root.attrib.get('ref')}, name: {t1_root.attrib.get('name')}")
            cols_list = []
            tc = t1_root.find('ns:tableColumns', ns) or t1_root.find('tableColumns')
            if tc is not None:
                for c in tc.findall('ns:tableColumn', ns) or tc.findall('tableColumn'):
                    cols_list.append(f"id={c.attrib.get('id')} name={c.attrib.get('name')}")
            output.append("Cols: " + ", ".join(cols_list))
        except Exception as te:
            output.append(f"Table1 error: {te}")

    os.makedirs(r"d:\FinHeal-Friend\f2-therapist-chatbot-backend\scratch", exist_ok=True)
    with open(r"d:\FinHeal-Friend\f2-therapist-chatbot-backend\scratch\generated_inspection.txt", "w", encoding="utf-8") as f_out:
        f_out.write("\n".join(output))
        
        # Add raw XML of row 25
        f_out.write("\n\n--- Row 25 Raw XML ---\n")
        if sheet_data is not None:
            for row in sheet_data.findall('ns:row', ns):
                if int(row.attrib.get('r', 1)) == 25:
                    f_out.write(ET.tostring(row, encoding='utf-8').decode('utf-8'))
                    
        f_out.write("\n\n--- Row 26 Raw XML ---\n")
        if sheet_data is not None:
            for row in sheet_data.findall('ns:row', ns):
                if int(row.attrib.get('r', 1)) == 26:
                    f_out.write(ET.tostring(row, encoding='utf-8').decode('utf-8'))
                    
    print("[DIAGNOSTIC] Generated inspection file successfully")
except Exception as e_diag:
    print(f"[DIAGNOSTIC] Error running diagnostic: {e_diag}")


