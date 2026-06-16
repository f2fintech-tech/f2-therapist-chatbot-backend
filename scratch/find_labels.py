import os
import xml.etree.ElementTree as ET
import zipfile

excel_path = r"d:\FinHeal-Friend\f2-therapist-chatbot-frontend\attached_assets\CAM_format\CAM_REPORT_FORMAT.xlsx"

with zipfile.ZipFile(excel_path, "r") as z:
    shared_strings = []
    if 'xl/sharedStrings.xml' in z.namelist():
        ss_content = z.read('xl/sharedStrings.xml')
        root = ET.fromstring(ss_content)
        ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        for si in root.findall('.//ns:si', ns):
            t_texts = [t.text for t in si.findall('.//ns:t', ns) if t.text]
            shared_strings.append("".join(t_texts) if t_texts else "")

    sheet1_xml = z.read("xl/worksheets/sheet1.xml")
    sheet_root = ET.fromstring(sheet1_xml)
    ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

    print("Searching for labels in original sheet:")
    for row in sheet_root.findall('.//ns:row', ns):
        r_num = int(row.attrib.get('r', 1))
        for c in row.findall('.//ns:c', ns):
            ref = c.attrib.get('r', '')
            t_type = c.attrib.get('t', '')
            v_elem = c.find('ns:v', ns)
            val = None
            if v_elem is not None and v_elem.text:
                val_str = v_elem.text
                if t_type == 's':
                    idx = int(val_str)
                    val = shared_strings[idx] if idx < len(shared_strings) else val_str
                else:
                    val = val_str
            if val and any(label in str(val) for label in ["NAME", "GENDER", "DOB", "AGE", "MOBILE", "EMAIL", "CIBIL", "LOANS", "EMI", "SECURED", "UNSECURED"]):
                print(f"Row {r_num:02d} | Cell {ref} | Value: {val}")
