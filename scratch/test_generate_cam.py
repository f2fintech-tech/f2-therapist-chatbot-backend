import zipfile
import xml.etree.ElementTree as ET
import re
import os

excel_path = r"d:\FinHeal-Friend\f2-therapist-chatbot-frontend\attached_assets\CAM_format\CAM_REPORT_FORMAT.xlsx"
import tempfile
out_path = os.path.join(tempfile.gettempdir(), 'test_cam_out.xlsx')

def test_xml_modify():
    print(f"Modifying template: {excel_path}")
    
    # Register the main namespace globally so ElementTree doesn't write tags with ns0 prefix
    main_ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    ET.register_namespace('', main_ns)
    
    import io
    bytes_io = io.BytesIO()
    
    with zipfile.ZipFile(excel_path, 'r') as zin:
        with zipfile.ZipFile(bytes_io, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                
                if item.filename == 'xl/worksheets/sheet1.xml':
                    print("Processing sheet1.xml...")
                    root = ET.fromstring(data)
                    ns = {'ns': main_ns}
                    
                    # 1. Modify Customer Name cell B2 to "John Test Doe"
                    b2_cell = None
                    # Find cell with r="B2"
                    for row in root.findall('.//ns:row', ns):
                        for c in row.findall('.//ns:c', ns):
                            if c.attrib.get('r') == 'B2':
                                b2_cell = c
                                break
                    
                    if b2_cell is not None:
                        print("Found cell B2, modifying to inlineStr 'John Test Doe'")
                        b2_cell.set('t', 'inlineStr')
                        # Remove existing <v> if any
                        v_elem = b2_cell.find('ns:v', ns)
                        if v_elem is not None:
                            b2_cell.remove(v_elem)
                        # Add <is><t>John Test Doe</t></is>
                        is_elem = ET.Element(f'{{{main_ns}}}is')
                        t_elem = ET.Element(f'{{{main_ns}}}t')
                        t_elem.text = "John Test Doe"
                        is_elem.append(t_elem)
                        b2_cell.append(is_elem)
                    
                    # 2. Modify CIBIL score cell B32 to 789
                    b32_cell = None
                    for row in root.findall('.//ns:row', ns):
                        for c in row.findall('.//ns:c', ns):
                            if c.attrib.get('r') == 'B32':
                                b32_cell = c
                                break
                    
                    if b32_cell is not None:
                        print("Found cell B32, modifying to number 789")
                        # Remove type attribute (numbers have no type attribute or t="n")
                        b32_cell.attrib.pop('t', None)
                        # Clear <is> if any
                        is_elem = b32_cell.find('ns:is', ns)
                        if is_elem is not None:
                            b32_cell.remove(is_elem)
                        # Find or create <v>
                        v_elem = b32_cell.find('ns:v', ns)
                        if v_elem is None:
                            v_elem = ET.Element(f'{{{main_ns}}}v')
                            b32_cell.append(v_elem)
                        v_elem.text = "789"
                    
                    # Write modified XML back
                    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
                    
                zout.writestr(item, data)

    with open(out_path, 'wb') as f:
        f.write(bytes_io.getvalue())

    print(f"Created test output workbook: {out_path}")

# Run modification
test_xml_modify()

# Inspect output to verify
print("\n--- Inspecting generated test Excel file ---")
import sys
sys.path.append(r"d:\FinHeal-Friend\f2-therapist-chatbot-backend\scratch")
from inspect_excel import inspect_xlsx_raw
inspect_xlsx_raw(out_path)
