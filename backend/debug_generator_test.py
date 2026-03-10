import sys
import os
import json

# Add current directory to sys.path so we can import app
sys.path.append(os.getcwd())

from app.core.simulation_generator import generate_simulation_config

prompt = "生成一个两个ai就钱是不是万能的辩论实验"
print(f"Testing with prompt: {prompt}")

try:
    config = generate_simulation_config(prompt)
    print("\n--- Result ---")
    print(json.dumps(config, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"\n--- Error ---")
    print(e)
    import traceback
    traceback.print_exc()
