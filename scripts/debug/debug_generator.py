import sys
import os
# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from dotenv import load_dotenv
load_dotenv("backend/.env")

from app.core.agent_generator import generate_adapter_code

model_name = "qwen-plus"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
usage_example = """
import os
from openai import OpenAI
client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)
completion = client.chat.completions.create(
    model="qwen-plus",
    messages=[{'role': 'user', 'content': '你是谁？'}]
)
print(completion.choices[0].message.content)
"""

print("Attempting to generate adapter code...")
try:
    code = generate_adapter_code(model_name, base_url, usage_example)
    if code:
        print("Code generation successful!")
        print("Length:", len(code))
        print("First 100 chars:", code[:100])
    else:
        print("Code generation returned empty string.")
        # Check if we can get the last error from adapter
        from app.core.adapter import get_last_response
        last = get_last_response()
        print("Last response from adapter:", last)
except Exception as e:
    print(f"Exception during generation: {e}")
    import traceback
    traceback.print_exc()
