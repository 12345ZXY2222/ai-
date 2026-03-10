
from pypdf import PdfReader
import os
import re

pdf_dir = "/home/peirm/ai模拟平台/论文/库存管理的比较/"
pdf_files = [
    "Sterman-ModelingManagerialBehavior-1989.pdf",
    "2505.18597v1.pdf",
    "2510.03310v1.pdf",
    "gijsbrechts-et-al-2022-can-deep-reinforcement-learning-improve-inventory-management-performance-on-lost-sales-dual.pdf"
]

keywords = [
    "demand distribution", "lead time", "holding cost", "shortage cost", "backorder cost", 
    "parameters", "experimental design", "setup", "newsvendor", "beer game", "lost sales"
]

for pdf_file in pdf_files:
    path = os.path.join(pdf_dir, pdf_file)
    print(f"--- Searching in {pdf_file} ---")
    try:
        reader = PdfReader(path)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
        
        # Search for keywords and print context
        found_contexts = []
        lines = full_text.split('\n')
        for i, line in enumerate(lines):
            for kw in keywords:
                if kw.lower() in line.lower():
                    # Get 5 lines before and after
                    start = max(0, i - 5)
                    end = min(len(lines), i + 6)
                    context = "\n".join(lines[start:end])
                    found_contexts.append(f"KEYWORD '{kw}':\n{context}\n")
                    break # Move to next line if keyword found
        
        # Print first 10 matches to avoid spam
        for ctx in found_contexts[:15]:
            print(ctx)
            print("-" * 20)
            
    except Exception as e:
        print(f"Error reading {pdf_file}: {e}")
