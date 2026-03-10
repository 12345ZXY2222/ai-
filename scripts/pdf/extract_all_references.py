
from pypdf import PdfReader
import os
import re

files = [
    "/home/peirm/ai模拟平台/论文/参考文献/From Individual to Society- A Survey on Social Simulation Driven by Large Language Model-based Agents.pdf",
    "/home/peirm/ai模拟平台/论文/参考文献/社会模拟演进A Survey on LLM-based Agents for Social Simulation- Taxonomy, Evaluation and Applications.pdf"
]

output_file = "all_references_extracted.txt"

with open(output_file, "w", encoding="utf-8") as f_out:
    for file_path in files:
        f_out.write(f"--- Processing {os.path.basename(file_path)} ---\n")
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            
            # Try to find References section
            # Common headers: References, Bibliography
            match = re.search(r'(References|Bibliography)\s*\n', text, re.IGNORECASE)
            if match:
                start_index = match.start()
                ref_text = text[start_index:]
                f_out.write(ref_text)
            else:
                f_out.write("Could not find References section. Dumping last 20% of text.\n")
                f_out.write(text[-len(text)//5:])
                
        except Exception as e:
            f_out.write(f"Error reading {file_path}: {e}\n")
        f_out.write("\n" + "="*50 + "\n")

print(f"References extracted to {output_file}")
