import json
from pathlib import Path
from typing import Any


# Use an absolute, stable data directory so persistence does not depend on
# the process working directory (cwd).
# This project stores JSON data under: backend/data/
DATA_DIR = (Path(__file__).resolve().parents[2] / "data").as_posix()
Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

def load_data(filename: str, default: Any) -> Any:
    filepath = str(Path(DATA_DIR) / filename)
    if Path(filepath).exists():
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            return default
    return default

def save_data(filename: str, data: Any):
    filepath = str(Path(DATA_DIR) / filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving {filename}: {e}")
