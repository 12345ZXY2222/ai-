import json
import numpy as np
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
artifacts_json = repo_root / "artifacts" / "results" / "bullwhip" / "bullwhip_reproduction_full.json"
legacy = Path("bullwhip_reproduction_full.json")
input_path = artifacts_json if artifacts_json.exists() else legacy

with input_path.open("r", encoding="utf-8") as f:
    data = json.load(f)

print("Variances:")
for model, results in data.items():
    print(f"--- {model} ---")
    for stage, orders in results.items():
        var = np.var(orders)
        print(f"{stage}: {var:.2f}")
