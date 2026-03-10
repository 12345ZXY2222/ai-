
import os
from pypdf import PdfReader

def search_pdf(path, keywords):
    try:
        reader = PdfReader(path)
        print(f"--- Searching {os.path.basename(path)} ---")
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            for kw in keywords:
                if kw.lower() in text.lower():
                    # Print context
                    idx = text.lower().find(kw.lower())
                    start = max(0, idx - 200)
                    end = min(len(text), idx + 200)
                    print(f"[Page {i+1}] ...{text[start:end].replace(chr(10), ' ')}...")
    except Exception as e:
        print(f"Error: {e}")

pdf_dir = "/home/peirm/ai模拟平台/论文/库存管理的比较/"
sterman = os.path.join(pdf_dir, "Sterman-ModelingManagerialBehavior-1989.pdf")
wang = os.path.join(pdf_dir, "2505.18597v1.pdf")

keywords = ["cost", "holding", "backlog", "delay", "initial", "prompt", "template", "instruction", "temperature", "gpt-4", "gpt-3.5", "demand"]

search_pdf(sterman, ["cost", "delay", "initial", "demand"])
print("\n" + "="*50 + "\n")
search_pdf(wang, ["prompt", "template", "cost", "holding", "backlog", "delay", "initial", "demand", "temperature"])
