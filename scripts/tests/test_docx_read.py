import zipfile
import xml.etree.ElementTree as ET
import os

def read_docx(file_path):
    try:
        with zipfile.ZipFile(file_path) as zf:
            xml_content = zf.read('word/document.xml')
        
        tree = ET.fromstring(xml_content)
        namespaces = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        }
        
        text_parts = []
        for node in tree.iter():
            if node.tag.endswith('}t'): # Text node
                if node.text:
                    text_parts.append(node.text)
            elif node.tag.endswith('}p'): # Paragraph
                text_parts.append('\n')
        
        return "".join(text_parts).strip()
    except Exception as e:
        return f"Error reading docx: {e}"

file_path = "backend/uploads/temp/日常经验取样问卷修改版.docx"
if os.path.exists(file_path):
    print(read_docx(file_path)[:500]) # Print first 500 chars
else:
    print("File not found")
