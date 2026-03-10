import os
import zipfile
import xml.etree.ElementTree as ET
import json
import logging
try:
    import pypdf
except ImportError:
    try:
        import PyPDF2 as pypdf
    except ImportError:
        pypdf = None

def extract_text_from_file(file_path: str) -> str:
    """
    Robustly extract text from various file formats (txt, md, json, docx, pdf).
    """
    if not os.path.exists(file_path):
        return ""
    
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        # 1. DOCX
        if ext == '.docx':
            return _read_docx(file_path)
        
        # 2. PDF
        elif ext == '.pdf':
            return _read_pdf(file_path)
            
        # 3. Text-based files
        else:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
                
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")
        return f"[Error reading file: {str(e)}]"

def _read_docx(file_path):
    try:
        with zipfile.ZipFile(file_path) as zf:
            xml_content = zf.read('word/document.xml')
        
        tree = ET.fromstring(xml_content)
        # Namespaces in Word XML
        namespaces = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        }
        
        text_parts = []
        # Iterate over all elements
        for node in tree.iter():
            # Check tag name ignoring namespace for simplicity or using simple string matching
            if 't' in node.tag and node.tag.endswith('}t'):
                if node.text:
                    text_parts.append(node.text)
            elif 'p' in node.tag and node.tag.endswith('}p'):
                text_parts.append('\n')
        
        return "".join(text_parts).strip()
    except Exception as e:
        return f"[Error parsing DOCX: {e}]"

def _read_pdf(file_path):
    if not pypdf:
        return "[Error: pypdf library not installed]"
    try:
        text = ""
        reader = pypdf.PdfReader(file_path)
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        return f"[Error parsing PDF: {e}]"
