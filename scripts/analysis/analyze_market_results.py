import pandas as pd
import os

RESULTS_DIR = "/home/peirm/ai模拟平台/论文/experiment_results"
posts_csv = os.path.join(RESULTS_DIR, "market_posts_llm_True.csv")

print("Loading data...")
df = pd.read_csv(posts_csv)

# 1. Profit Analysis
# Get initial and final wealth for each agent
# Initial: Step 0, Final: Step 199
initial_wealth = df[df['Step'] == 0].set_index('AgentID')['Wealth']
final_wealth = df[df['Step'] == 199].set_index('AgentID')['Wealth']
agent_types = df[df['Step'] == 0].set_index('AgentID')['Type']

profit = final_wealth - initial_wealth
profit_df = pd.DataFrame({'Type': agent_types, 'Profit': profit})

print("\n--- Profit Analysis by Group ---")
print(profit_df.groupby('Type')['Profit'].describe())

# 2. Sentiment/Post Analysis
# Filter for LLM_Social agents around the shock time (Step 100-120)
shock_df = df[(df['Step'] >= 100) & (df['Step'] <= 120)]
llm_posts = shock_df[shock_df['Type'] == 'LLM_Social']['Post'].unique()

print("\n--- LLM Social Posts during Bubble Formation (Step 100-120) ---")
for post in llm_posts[:10]:
    print(f"- {post}")

# 3. Action Analysis
print("\n--- Action Distribution by Group (Step 100-120) ---")
print(shock_df.groupby(['Type', 'Action']).size().unstack(fill_value=0))
