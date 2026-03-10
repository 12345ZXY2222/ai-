
import os
from pypdf import PdfReader

pdf_dir = "/home/peirm/ai模拟平台/论文/库存管理的比较/"
files = [f for f in os.listdir(pdf_dir) if f.endswith(".pdf")]

for f in files:
    path = os.path.join(pdf_dir, f)
    try:
        reader = PdfReader(path)
        page = reader.pages[0]
        text = page.extract_text()
        print(f"--- File: {f} ---")
        print(text[:500])
        print("\n")
    except Exception as e:
        print(f"Error reading {f}: {e}")
