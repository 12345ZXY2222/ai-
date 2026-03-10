
from pypdf import PdfReader

reader = PdfReader("/home/peirm/ai模拟平台/example/LLMs for Supply Chain Management.pdf")
text = ""
for page in reader.pages:
    text += page.extract_text() + "\n"

print(text)
