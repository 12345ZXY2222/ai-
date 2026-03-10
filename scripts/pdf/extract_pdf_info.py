
from pypdf import PdfReader
import os

pdf_dir = "/home/peirm/ai模拟平台/论文/库存管理的比较/"
pdf_files = [
    "Sterman-ModelingManagerialBehavior-1989.pdf",
    "2505.18597v1.pdf",
    "2510.03310v1.pdf",
    "gijsbrechts-et-al-2022-can-deep-reinforcement-learning-improve-inventory-management-performance-on-lost-sales-dual.pdf"
]

for pdf_file in pdf_files:
    path = os.path.join(pdf_dir, pdf_file)
    print(f"--- Processing {pdf_file} ---")
    try:
        reader = PdfReader(path)
        # Read first 5 pages for abstract and intro/setup
        text = ""
        num_pages = min(len(reader.pages), 5)
        for i in range(num_pages):
            text += reader.pages[i].extract_text() + "\n"
        
        # Also try to find "Experimental Design" or "Parameters" sections later in the doc if possible
        # But for now let's just dump the beginning to identify the paper and key setup
        print(text[:5000]) # Limit output size
        print("\n" + "="*50 + "\n")
    except Exception as e:
        print(f"Error reading {pdf_file}: {e}")
