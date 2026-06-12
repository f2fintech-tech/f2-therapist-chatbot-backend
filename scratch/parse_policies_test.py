import zipfile
import xml.etree.ElementTree as ET
import os
from pathlib import Path

def get_docx_markdown(docx_path):
    try:
        doc = zipfile.ZipFile(docx_path)
        xml_content = doc.read('word/document.xml')
        root = ET.fromstring(xml_content)
        
        # Word XML namespaces
        ns = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        }
        
        markdown_lines = []
        for p in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
            # Check for paragraph properties
            pPr = p.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr')
            pStyle = None
            is_bullet = False
            
            if pPr is not None:
                pStyle_node = pPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pStyle')
                if pStyle_node is not None:
                    pStyle = pStyle_node.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                
                numPr = pPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numPr')
                if numPr is not None:
                    is_bullet = True
            
            # Extract text segments inside runs
            text_segments = []
            for r in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r'):
                # Check if text is bold
                rPr = r.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr')
                is_bold = False
                if rPr is not None:
                    b = rPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}b')
                    if b is not None:
                        is_bold = True
                
                t_node = r.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
                if t_node is not None and t_node.text:
                    txt = t_node.text
                    if is_bold and txt.strip():
                        # Handle bold styling in markdown
                        text_segments.append(f"**{txt}**")
                    else:
                        text_segments.append(txt)
            
            p_text = "".join(text_segments).strip()
            
            # Formatting line based on style
            if p_text:
                if pStyle in ['Heading1', 'Heading2', 'Heading3', 'Title']:
                    # Map headings to markdown headers
                    level = 1 if pStyle in ['Heading1', 'Title'] else (2 if pStyle == 'Heading2' else 3)
                    markdown_lines.append(f"{'#' * level} {p_text}")
                elif is_bullet:
                    markdown_lines.append(f"- {p_text}")
                else:
                    # Check if the text looks like a heading (short, bold, no punctuation at end)
                    if p_text.startswith("**") and p_text.endswith("**") and len(p_text) < 100:
                        markdown_lines.append(f"### {p_text.replace('**', '')}")
                    else:
                        markdown_lines.append(p_text)
            else:
                markdown_lines.append("")
        
        # Clean up consecutive empty lines
        cleaned_lines = []
        for line in markdown_lines:
            if not line and cleaned_lines and not cleaned_lines[-1]:
                continue
            cleaned_lines.append(line)
            
        return "\n".join(cleaned_lines).strip()
    except Exception as e:
        print(f"Error parsing {docx_path}: {e}")
        return ""

def main():
    policies_dir = Path(r"d:\FinHeal-Friend\f2-therapist-chatbot-frontend\attached_assets\policies")
    for f in policies_dir.glob("*.docx"):
        print(f"File: {f.name}")
        md = get_docx_markdown(f)
        print("Preview:")
        print("\n".join(md.split("\n")[:10]))
        print("-" * 50)

if __name__ == "__main__":
    main()
