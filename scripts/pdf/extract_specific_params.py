
from pypdf import PdfReader
import os

pdf_dir = "/home/peirm/ai模拟平台/论文/库存管理的比较/"
files_to_check = {
    "Sterman-ModelingManagerialBehavior-1989.pdf": ["stockout cost", "backlog cost", "customer demand", "orders"],
    "2510.03310v1.pdf": ["Schweitzer", "Cachon", "Chen et al", "selling price", "unit cost", "uniform distribution", "demand"],
    "gijsbrechts-et-al-2022-can-deep-reinforcement-learning-improve-inventory-management-performance-on-lost-sales-dual.pdf": ["numerical study", "parameter settings", "lead time", "lost sales model", "poisson"]
}

for pdf_file, keywords in files_to_check.items():
    path = os.path.join(pdf_dir, pdf_file)
    print(f"--- Searching in {pdf_file} ---")
    try:
        reader = PdfReader(path)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
        
        lines = full_text.split('\n')
        for i, line in enumerate(lines):
            for kw in keywords:
                if kw.lower() in line.lower():
                    # Print context
                    start = max(0, i - 3)
                    end = min(len(lines), i + 4)
                    print(f"MATCH '{kw}':")
                    print("\n".join(lines[start:end]))
                    print("-" * 20)
    except Exception as e:
        print(f"Error reading {pdf_file}: {e}")
