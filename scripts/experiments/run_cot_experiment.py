import sys
import os
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from run_market_simulation import run_market_simulation

RESULTS_DIR = str(REPO_ROOT / "论文" / "experiment_results")

# Scenarios: Compare Standard LLM vs CoT LLM in High Volatility
scenarios = [
    {"use_llm": True, "lambda_adj": 0.01, "use_cot": False}, # Standard
    {"use_llm": True, "lambda_adj": 0.01, "use_cot": True},  # CoT
    {"use_llm": True, "lambda_adj": 0.002, "use_cot": False}, # Standard Low Vol
    {"use_llm": True, "lambda_adj": 0.002, "use_cot": True}   # CoT Low Vol
]

print("Starting CoT Experiment Simulations...")
for s in scenarios:
    print(f"\n>>> Running Scenario: LLM={s['use_llm']}, Lambda={s['lambda_adj']}, CoT={s['use_cot']}")
    # Check if result already exists to avoid re-running if interrupted
    suffix = f"llm_{s['use_llm']}_lambda_{s['lambda_adj']}_v2_cot_{s['use_cot']}"
    csv_path = os.path.join(RESULTS_DIR, f"market_simulation_{suffix}.csv")
    
    if os.path.exists(csv_path):
        print(f"Skipping {suffix}, already exists.")
    else:
        run_market_simulation(use_llm=s['use_llm'], lambda_adj=s['lambda_adj'], version="v2", use_cot=s['use_cot'])

print("\nAll simulations completed. Starting Analysis...")

# Analysis
analysis_scenarios = [
    {"name": "High_Standard", "file_suffix": "llm_True_lambda_0.01_v2_cot_False"},
    {"name": "High_CoT",      "file_suffix": "llm_True_lambda_0.01_v2_cot_True"},
    {"name": "Low_Standard",  "file_suffix": "llm_True_lambda_0.002_v2_cot_False"},
    {"name": "Low_CoT",       "file_suffix": "llm_True_lambda_0.002_v2_cot_True"}
]

results = []

for s in analysis_scenarios:
    sim_csv = os.path.join(RESULTS_DIR, f"market_simulation_{s['file_suffix']}.csv")
    posts_csv = os.path.join(RESULTS_DIR, f"market_posts_{s['file_suffix']}.csv")
    
    if not os.path.exists(sim_csv):
        print(f"Warning: {sim_csv} not found.")
        continue
        
    df_sim = pd.read_csv(sim_csv)
    df_posts = pd.read_csv(posts_csv)
    
    # 1. Volatility
    max_price = df_sim['Price'].max()
    peak_step = df_sim['Price'].idxmax()
    final_price = df_sim['Price'].iloc[-1]
    volatility = df_sim['Price'].std()
    
    # 2. Wealth
    initial_wealth = df_posts[df_posts['Step'] == 0].set_index('AgentID')['Wealth']
    final_wealth = df_posts[df_posts['Step'] == 199].set_index('AgentID')['Wealth']
    agent_types = df_posts[df_posts['Step'] == 0].set_index('AgentID')['Type']
    
    profit = final_wealth - initial_wealth
    profit_df = pd.DataFrame({'Type': agent_types, 'Profit': profit})
    avg_profit = profit_df.groupby('Type')['Profit'].mean()
    
    res = {
        "Scenario": s['name'],
        "Peak_Step": peak_step,
        "Max_Price": max_price,
        "Final_Price": final_price,
        "Volatility": volatility,
        "Profit_Fund": avg_profit.get('Fundamental', 0),
        "Profit_Tech": avg_profit.get('Technical', 0),
        "Profit_Soc": avg_profit.get('Social', 0),
        "Profit_LLM": avg_profit.get('LLM_Social', 0)
    }
    results.append(res)

df_res = pd.DataFrame(results)
output_file = os.path.join(RESULTS_DIR, "cot_experiment_analysis.csv")
df_res.to_csv(output_file, index=False)

print("\n--- CoT Experiment Comparative Analysis ---")
print(df_res.to_string(index=False))
print(f"\nAnalysis saved to {output_file}")

