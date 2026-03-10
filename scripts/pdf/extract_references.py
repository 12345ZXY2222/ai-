
from pypdf import PdfReader
import os

files = [
    "/home/peirm/ai模拟平台/论文/参考文献/From Individual to Society- A Survey on Social Simulation Driven by Large Language Model-based Agents.pdf",
    "/home/peirm/ai模拟平台/论文/参考文献/社会模拟演进A Survey on LLM-based Agents for Social Simulation- Taxonomy, Evaluation and Applications.pdf"
]

for file_path in files:
    print(f"--- Processing {os.path.basename(file_path)} ---")
    try:
        reader = PdfReader(file_path)
        text = ""
        # Read the last few pages where references usually are
        num_pages = len(reader.pages)
        start_page = max(0, num_pages - 5) # Read last 5 pages
        
        for i in range(start_page, num_pages):
            text += reader.pages[i].extract_text() + "\n"
            
        print(text)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    print("\n" + "="*50 + "\n")
