import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from run_market_simulation import run_market_simulation

# Scenarios
scenarios = [
    {"use_llm": False, "lambda_adj": 0.01}, # High Volatility, No LLM
    {"use_llm": True, "lambda_adj": 0.01},  # High Volatility, With LLM
    {"use_llm": False, "lambda_adj": 0.002}, # Low Volatility, No LLM
    {"use_llm": True, "lambda_adj": 0.002}   # Low Volatility, With LLM
]

for s in scenarios:
    print(f"\n>>> Running Scenario: LLM={s['use_llm']}, Lambda={s['lambda_adj']}")
    run_market_simulation(use_llm=s['use_llm'], lambda_adj=s['lambda_adj'], version="v2")

print("\nAll scenarios completed.")
