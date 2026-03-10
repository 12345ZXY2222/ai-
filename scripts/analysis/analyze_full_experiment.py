import pandas as pd
import os
import numpy as np

RESULTS_DIR = "/home/peirm/ai模拟平台/论文/experiment_results"

scenarios = [
    {"name": "High_NoLLM", "file_suffix": "llm_False_lambda_0.01_v2"},
    {"name": "High_LLM", "file_suffix": "llm_True_lambda_0.01_v2"},
    {"name": "Low_NoLLM", "file_suffix": "llm_False_lambda_0.002_v2"},
    {"name": "Low_LLM", "file_suffix": "llm_True_lambda_0.002_v2"}
]

results = []

for s in scenarios:
    sim_csv = os.path.join(RESULTS_DIR, f"market_simulation_{s['file_suffix']}.csv")
    posts_csv = os.path.join(RESULTS_DIR, f"market_posts_{s['file_suffix']}.csv")
    
    if not os.path.exists(sim_csv):
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
    
    # 3. LLM Posts Analysis (for Low_LLM)
    if s['name'] == "Low_LLM":
        print("\n--- LLM Posts in Low Volatility Scenario (Step 100-110) ---")
        shock_posts = df_posts[(df_posts['Step'] >= 100) & (df_posts['Step'] <= 110) & (df_posts['Type'] == 'LLM_Social')]
        unique_posts = shock_posts['Post'].unique()
        for p in unique_posts[:5]:
            print(f"- {p}")

df_res = pd.DataFrame(results)
print("\n--- Comparative Analysis ---")
print(df_res.to_string(index=False))
