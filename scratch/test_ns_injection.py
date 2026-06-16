import re

# Mock a serialized XML string
file_bytes = b'''<?xml version='1.0' encoding='utf-8'?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:xr="http://schemas.microsoft.com/office/spreadsheetml/2014/revision" mc:Ignorable="x14ac xr xr2 xr3" xr:uid="{00000000-0001-0000-0000-000000000000}"><sheetPr codeName="Sheet1" /></worksheet>'''

missing_decls = []
if b'xmlns:x14ac=' not in file_bytes:
    missing_decls.append(b'xmlns:x14ac="http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac"')
if b'xmlns:xr2=' not in file_bytes:
    missing_decls.append(b'xmlns:xr2="http://schemas.microsoft.com/office/spreadsheetml/2015/revision2"')
if b'xmlns:xr3=' not in file_bytes:
    missing_decls.append(b'xmlns:xr3="http://schemas.microsoft.com/office/spreadsheetml/2016/revision3"')

if missing_decls:
    decls_str = b' ' + b' '.join(missing_decls)
    file_bytes = file_bytes.replace(b'<worksheet', b'<worksheet' + decls_str, 1)

print("Modified XML:")
print(file_bytes.decode('utf-8')[:500])
