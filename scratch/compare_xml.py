import os
import sys
import xml.etree.ElementTree as ET
import zipfile
import tempfile

backend_dir = r"d:\FinHeal-Friend\f2-therapist-chatbot-backend"
excel_path = r"d:\FinHeal-Friend\f2-therapist-chatbot-frontend\attached_assets\CAM_format\CAM_REPORT_FORMAT.xlsx"
out_path = os.path.join(tempfile.gettempdir(), "test_generated_output.xlsx")

with zipfile.ZipFile(excel_path, "r") as z:
    orig_sheet1_xml = z.read("xl/worksheets/sheet1.xml")

with zipfile.ZipFile(out_path, "r") as z:
    gen_sheet1_xml = z.read("xl/worksheets/sheet1.xml")

print("--- ORIGINAL SHEET1.XML (First 1000 chars) ---")
print(orig_sheet1_xml[:1000].decode('utf-8'))
print("\n--- GENERATED SHEET1.XML (First 1000 chars) ---")
print(gen_sheet1_xml[:1000].decode('utf-8'))
