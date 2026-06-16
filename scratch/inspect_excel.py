import zipfile
import xml.etree.ElementTree as ET
import re
import sys

# Reconfigure stdout to use UTF-8 to prevent CP1252 encoding crashes on Windows terminal
sys.stdout.reconfigure(encoding='utf-8')

excel_path = r"d:\FinHeal-Friend\f2-therapist-chatbot-frontend\attached_assets\CAM_format\CAM_REPORT_FORMAT.xlsx"

def inspect_xlsx_raw(path):
    print(f"Opening ZIP archive: {path}")
    with zipfile.ZipFile(path, 'r') as z:
        # 1. Load shared strings
        shared_strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            ss_content = z.read('xl/sharedStrings.xml')
            root = ET.fromstring(ss_content)
            ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            for si in root.findall('.//ns:si', ns):
                t_texts = [t.text for t in si.findall('.//ns:t', ns) if t.text]
                shared_strings.append("".join(t_texts) if t_texts else "")
            print(f"Loaded {len(shared_strings)} shared strings.")

        # 2. Get sheet names and files
        sheets = []
        wb_content = z.read('xl/workbook.xml')
        wb_root = ET.fromstring(wb_content)
        ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        for sheet in wb_root.findall('.//ns:sheet', ns):
            name = sheet.attrib.get('name')
            sheet_id = sheet.attrib.get('sheetId')
            sheets.append((name, sheet_id))
        print(f"Sheets in workbook: {sheets}")

        # 3. Read sheet data
        for index, (name, s_id) in enumerate(sheets):
            sheet_file = f'xl/worksheets/sheet{s_id}.xml'
            if sheet_file not in z.namelist():
                worksheets = [f for f in z.namelist() if f.startswith('xl/worksheets/sheet')]
                if index < len(worksheets):
                    sheet_file = worksheets[index]
                else:
                    continue

            print(f"\n--- Reading Sheet: {name} (File: {sheet_file}) ---")
            sheet_content = z.read(sheet_file)
            sheet_root = ET.fromstring(sheet_content)

            cells_data = {}
            max_r = 1
            max_c = 1

            for row in sheet_root.findall('.//ns:row', ns):
                r_num = int(row.attrib.get('r', 1))
                max_r = max(max_r, r_num)
                for c in row.findall('.//ns:c', ns):
                    ref = c.attrib.get('r', '')
                    match = re.match(r'([A-Z]+)([0-9]+)', ref)
                    if match:
                        col_str, row_str = match.groups()
                        col_idx = 0
                        for char in col_str:
                            col_idx = col_idx * 26 + (ord(char) - ord('A') + 1)
                        max_c = max(max_c, col_idx)
                    else:
                        continue

                    # Get value
                    t_type = c.attrib.get('t', '')
                    v_elem = c.find('ns:v', ns)
                    val = None
                    if v_elem is not None and v_elem.text:
                        val_str = v_elem.text
                        if t_type == 's':  # Shared string
                            idx = int(val_str)
                            val = shared_strings[idx] if idx < len(shared_strings) else val_str
                        elif t_type == 'b':  # Boolean
                            val = (val_str == '1')
                        else:
                            try:
                                if '.' in val_str:
                                    val = float(val_str)
                                else:
                                    val = int(val_str)
                            except ValueError:
                                val = val_str
                    cells_data[(r_num, col_idx)] = val

            print(f"Max detected rows: {max_r}, Max columns: {max_c}")
            for r in range(1, max_r + 1):
                row_vals = [cells_data.get((r, col)) for col in range(1, max_c + 1)]
                if any(v is not None for v in row_vals):
                    formatted = []
                    for v in row_vals:
                        if v is None:
                            formatted.append("")
                        else:
                            formatted.append(str(v).replace('\n', ' '))
                    # Clean printed output columns
                    print(f"Row {r:02d}: {formatted}")

inspect_xlsx_raw(excel_path)
