import pandas as pd
import os
import matplotlib.pyplot as plt

RESULTS_DIR = "/home/peirm/ai模拟平台/论文/experiment_results"

def analyze_scenario(use_llm):
    suffix = str(use_llm)
    posts_csv = os.path.join(RESULTS_DIR, f"market_posts_llm_{suffix}.csv")
    sim_csv = os.path.join(RESULTS_DIR, f"market_simulation_llm_{suffix}.csv")
    
    if not os.path.exists(posts_csv) or not os.path.exists(sim_csv):
        print(f"Data for LLM={suffix} not found.")
        return None

    # Load Data
    df_posts = pd.read_csv(posts_csv)
    df_sim = pd.read_csv(sim_csv)
    
    # 1. Wealth Analysis
    initial_wealth = df_posts[df_posts['Step'] == 0].set_index('AgentID')['Wealth']
    final_wealth = df_posts[df_posts['Step'] == 199].set_index('AgentID')['Wealth']
    agent_types = df_posts[df_posts['Step'] == 0].set_index('AgentID')['Type']
    
    profit = final_wealth - initial_wealth
    profit_df = pd.DataFrame({'Type': agent_types, 'Profit': profit})
    avg_profit = profit_df.groupby('Type')['Profit'].mean()
    
    # 2. Bubble Analysis
    # Find max price deviation from True Value
    df_sim['Deviation'] = df_sim['Price'] - df_sim['True_Value']
    max_bubble = df_sim['Deviation'].max()
    peak_step = df_sim['Price'].idxmax()
    
    return {
        'avg_profit': avg_profit,
        'max_bubble': max_bubble,
        'peak_step': peak_step,
        'final_price': df_sim['Price'].iloc[-1]
    }

print("--- Comparing Scenarios ---")
results_no_llm = analyze_scenario(False)
results_llm = analyze_scenario(True)

if results_no_llm and results_llm:
    print("\n[Wealth Comparison (Avg Profit)]")
    print(f"{'Type':<15} | {'No LLM':<10} | {'With LLM':<10}")
    print("-" * 40)
    all_types = set(results_no_llm['avg_profit'].index) | set(results_llm['avg_profit'].index)
    for t in all_types:
        val_no = results_no_llm['avg_profit'].get(t, 0)
        val_llm = results_llm['avg_profit'].get(t, 0)
        print(f"{t:<15} | {val_no:>10.2f} | {val_llm:>10.2f}")

    print("\n[Bubble Dynamics]")
    print(f"{'Metric':<20} | {'No LLM':<10} | {'With LLM':<10}")
    print("-" * 45)
    print(f"{'Max Bubble Size':<20} | {results_no_llm['max_bubble']:>10.2f} | {results_llm['max_bubble']:>10.2f}")
    print(f"{'Peak Step':<20} | {results_no_llm['peak_step']:>10} | {results_llm['peak_step']:>10}")
    print(f"{'Final Price':<20} | {results_no_llm['final_price']:>10.2f} | {results_llm['final_price']:>10.2f}")
