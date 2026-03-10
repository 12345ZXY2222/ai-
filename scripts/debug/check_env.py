import os
from dotenv import load_dotenv

load_dotenv("backend/.env")

key = os.getenv("DEEPSEEK_API_KEY")
if key:
    print("DEEPSEEK_API_KEY is set.")
    if key.startswith("sk-"):
        print("Key format looks correct (starts with sk-).")
    else:
        print("Key format might be unusual.")
else:
    print("DEEPSEEK_API_KEY is NOT set.")

provider = os.getenv("AI_PROVIDER")
print(f"AI_PROVIDER is: {provider}")
