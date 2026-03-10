import pandas as pd
import os
import matplotlib.pyplot as plt

RESULTS_DIR = "/home/peirm/ai模拟平台/论文/experiment_results"
# Use the High Volatility LLM scenario
posts_csv = os.path.join(RESULTS_DIR, "market_posts_llm_True_lambda_0.01.csv")
sim_csv = os.path.join(RESULTS_DIR, "market_simulation_llm_True_lambda_0.01.csv")

df_posts = pd.read_csv(posts_csv)
df_sim = pd.read_csv(sim_csv)

# Identify Peak
peak_step = df_sim['Price'].idxmax()
peak_price = df_sim['Price'].max()
print(f"Peak Step: {peak_step}, Peak Price: {peak_price:.2f}")

# Define "Crash Phase" (Peak to Peak+20)
crash_start = peak_step
crash_end = peak_step + 20

print(f"\nAnalyzing Selling Behavior during Crash Phase (Step {crash_start}-{crash_end})...")

crash_data = df_posts[(df_posts['Step'] >= crash_start) & (df_posts['Step'] <= crash_end)]

# Count Sells by Type
sell_counts = crash_data[crash_data['Action'] == 'SELL'].groupby('Type').size()
print("\nSell Orders during Crash:")
print(sell_counts)

# Calculate Average Sell Price by Type
# We need to merge with price data to get exact price at that step
crash_data = crash_data.merge(df_sim[['Step', 'Price']], on='Step')
crash_sells = crash_data[crash_data['Action'] == 'SELL']
avg_sell_price = crash_sells.groupby('Type')['Price'].mean()

print("\nAverage Sell Price during Crash:")
print(avg_sell_price)

# Compare with Fundamental Traders
fund_sells = sell_counts.get('Fundamental', 0)
llm_sells = sell_counts.get('LLM_Social', 0)
soc_sells = sell_counts.get('Social', 0)

print(f"\nAnalysis:")
print(f"Fundamental Traders sold {fund_sells} times.")
print(f"LLM Traders sold {llm_sells} times.")
print(f"Rule-based Social Traders sold {soc_sells} times.")

# Analyze Buying Behavior during Recovery/Dip (e.g., Price < True Value)
# True Value is approx 110.
print("\nAnalyzing Buying Behavior when Price < True Value (Value Investing)...")
undervalued_data = df_sim[df_sim['Price'] < df_sim['True_Value'] * 0.9]
if not undervalued_data.empty:
    steps = undervalued_data['Step'].tolist()
    buy_data = df_posts[(df_posts['Step'].isin(steps)) & (df_posts['Action'] == 'BUY')]
    
    buy_counts = buy_data.groupby('Type').size()
    print("\nBuy Orders when Undervalued:")
    print(buy_counts)
    
    avg_buy_price = buy_data.groupby('Type')['Price'].mean()
    print("\nAverage Buy Price when Undervalued:")
    print(avg_buy_price)
else:
    print("No undervalued period found.")
