
import os
from pypdf import PdfReader

def extract_prompts(path):
    try:
        reader = PdfReader(path)
        print(f"--- Extracting Prompts from {os.path.basename(path)} ---")
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
            
        # Search for prompt sections
        markers = ["Risk Aversion Agent Prompt", "Risk Neutral Agent Prompt", "Risk Appetite Agent Prompt", "Risk Seeking Agent Prompt"]
        
        for marker in markers:
            if marker in full_text:
                print(f"\n=== {marker} ===")
                start = full_text.find(marker)
                # Extract a chunk after the marker
                print(full_text[start:start+1000])
                
    except Exception as e:
        print(f"Error: {e}")

pdf_dir = "/home/peirm/ai模拟平台/论文/库存管理的比较/"
wang = os.path.join(pdf_dir, "2505.18597v1.pdf")

extract_prompts(wang)
