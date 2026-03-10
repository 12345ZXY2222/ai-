import json
import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from jinja2 import Template
import re
import numpy as np
import random

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))
os.environ['AI_PROVIDER'] = 'deepseek'

try:
    from app.core.adapter import ai_chat
except ImportError as e:
    print(f"Error importing ai_chat: {e}")
    # Mock for testing if backend not available
    def ai_chat(**kwargs):
        return {"content": "```json\n{\"order_quantity\": 20}\n```"}

# --- Configuration ---
AGENTS_FILE = "/home/peirm/ai模拟平台/backend/data/agents.json"
RESULTS_DIR = "/home/peirm/ai模拟平台/论文/experiment_results"
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

MODELS = {
    "DeepSeek": "18b70aa2-a723-45be-9766-36f4bcc159a2",
    "Qwen": "ebe7051f-eb87-4eae-9224-f4c2183b4b47"
}

# --- Parameters ---
MEAN_DEMAND = 20
STD_DEMAND = 5
LEAD_TIME = 2
HOLDING_COST = 1
SHORTAGE_COST = 10
ORDERING_COST = 2
SELLING_PRICE = 15
INITIAL_INVENTORY = 20
PERIODS = 10
RUNS = 3

# --- Helper Functions ---
def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def extract_json(text):
    if not isinstance(text, str): return text
    try:
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match: return json.loads(match.group(1))
        match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match: return json.loads(match.group(1))
        # Try finding a simple json object
        match = re.search(r"\{.*?\}", text, re.DOTALL)
        if match: return json.loads(match.group(0))
        return json.loads(text)
    except:
        return {}

def calculate_optimal_base_stock():
    # Critical Ratio
    cr = SHORTAGE_COST / (SHORTAGE_COST + HOLDING_COST)
    # Demand during L+1 periods
    # Mean = (L+1) * mu
    # Std = sqrt(L+1) * sigma
    l_plus_1 = LEAD_TIME + 1
    mu_l = l_plus_1 * MEAN_DEMAND
    sigma_l = np.sqrt(l_plus_1) * STD_DEMAND
    
    # Inverse CDF (Percent Point Function)
    from statistics import NormalDist
    s_star = NormalDist(mu=mu_l, sigma=sigma_l).inv_cdf(cr)
    return s_star

# --- Simulation Logic ---

def run_inventory_episode(agent_func, demand_seq, role_name="AI"):
    # State
    inventory = INITIAL_INVENTORY
    # Pipeline: list of orders. pipeline[0] arrives in 1 period (start of next), pipeline[1] in 2 periods...
    # Actually, let's track orders by arrival time.
    # If L=2, order at t arrives at t+2.
    # So at t, we have orders arriving at t+1, t+2...
    # Let's use a list where index 0 is arriving next period (t+1).
    # pipeline = [q_arriving_t+1]
    pipeline = [0] * (LEAD_TIME - 1) 
    
    history = []
    total_profit = 0
    
    records = []
    
    for t in range(1, PERIODS + 1):
        # 1. Receive Shipment (Already in inventory? No, we defined sequence: Receive -> Decide -> Demand)
        # But pipeline[0] is arriving at t? No, we said pipeline[0] arrives at t+1.
        # Let's refine:
        # At start of t, order placed at t-L arrives.
        # We handle this by having a queue.
        # Let's say queue has size L.
        # queue[0] arrives now. queue[1] arrives next...
        
        # Initialize queue with 0s
        if t == 1:
            # queue of orders placed at t-2, t-1.
            # Assume 0 orders placed before.
            incoming_orders = [0] * LEAD_TIME 
        
        arrived_qty = incoming_orders.pop(0)
        inventory += arrived_qty
        
        # 2. Observation
        # Pipeline now contains orders arriving t+1, t+2...
        # incoming_orders has length L-1.
        
        state_desc = {
            "period": t,
            "inventory": inventory,
            "pipeline": list(incoming_orders), # Copy
            "history": history[-3:] # Last 3 entries to save tokens
        }
        
        # 3. Decision
        if role_name == "Optimal":
            # Base Stock Policy
            # Inventory Position = On-hand + On-order - Backorder
            # On-order = sum(incoming_orders)
            # Backorder is negative inventory
            inv_pos = inventory + sum(incoming_orders)
            s_star = calculate_optimal_base_stock()
            order_qty = max(0, int(s_star - inv_pos))
        else:
            # AI Agent
            order_qty = agent_func(state_desc)
        
        # 4. Place Order
        incoming_orders.append(order_qty) # Arrives in L periods (at start of t+L)
        
        # 5. Demand
        demand = demand_seq[t-1]
        
        # 6. Update Inventory & Costs
        # Sales = min(Demand, max(0, inventory)) ? 
        # If backlog allowed:
        inventory -= demand
        
        holding_cost = max(0, inventory) * HOLDING_COST
        shortage_cost = max(0, -inventory) * SHORTAGE_COST
        ordering_cost = order_qty * ORDERING_COST
        
        # Revenue: We sell 'demand' units eventually? 
        # Or revenue on sales?
        # Standard backlog: Revenue is r * demand (since we fulfill it eventually).
        # But we pay shortage cost for delay.
        revenue = demand * SELLING_PRICE
        
        period_profit = revenue - holding_cost - shortage_cost - ordering_cost
        total_profit += period_profit
        
        # Log
        rec = {
            "Period": t,
            "Arrived": arrived_qty,
            "Inventory_Start": inventory + demand, # Before demand
            "Demand": demand,
            "Inventory_End": inventory,
            "Order": order_qty,
            "Profit": period_profit,
            "Total_Profit": total_profit
        }
        records.append(rec)
        history.append(f"Period {t}: Start Inv={rec['Inventory_Start']}, Demand={demand}, Order={order_qty}, Profit={period_profit}")
        
    return total_profit, records

def main():
    print("Starting Inventory Management Experiment...")
    
    agents_db = load_json(AGENTS_FILE)
    all_results = []
    
    # Generate Demand Sequences (Common Random Numbers)
    np.random.seed(42)
    demand_scenarios = []
    for i in range(RUNS):
        # Round to nearest integer, non-negative
        d = np.maximum(0, np.round(np.random.normal(MEAN_DEMAND, STD_DEMAND, PERIODS))).astype(int)
        demand_scenarios.append(d)
        
    # 1. Run Optimal Benchmark
    print("Running Optimal Benchmark...")
    opt_profits = []
    for i in range(RUNS):
        profit, records = run_inventory_episode(None, demand_scenarios[i], role_name="Optimal")
        opt_profits.append(profit)
        for r in records:
            r["Model"] = "Optimal (Base Stock)"
            r["Run"] = i + 1
            all_results.append(r)
            
            # 2. Run AI Models (Standard)
    for model_name, model_id in MODELS.items():
        print(f"Running {model_name} (Standard)...")
        agent_conf = agents_db.get(model_id)
        
        for i in range(RUNS):
            print(f"  Run {i+1}/{RUNS}")
            
            def ai_agent_standard(state):
                prompt = f"""You are a Supply Chain Manager.
Goal: Maximize Total Profit over {PERIODS} periods.
Parameters:
- Holding Cost: ${HOLDING_COST}/unit/period (for positive inventory)
- Shortage Penalty: ${SHORTAGE_COST}/unit/period (for negative inventory/backlog)
- Ordering Cost: ${ORDERING_COST}/unit
- Selling Price: ${SELLING_PRICE}/unit
- Demand: Normal Distribution (Mean={MEAN_DEMAND}, Std={STD_DEMAND})
- Lead Time: {LEAD_TIME} periods (Order placed now arrives in {LEAD_TIME} periods).

Current State (Period {state['period']}):
- On-hand Inventory: {state['inventory']}
- Pipeline (Incoming Orders): {state['pipeline']} (First item arrives next period)

History:
{chr(10).join(state['history'])}

How many units do you want to order now?
Reply JSON: {{"order_quantity": integer}}"""

                try:
                    response = ai_chat(
                        messages_or_prompt=[{"role": "user", "content": prompt}],
                        prompt_content=prompt,
                        model=agent_conf.get("model"),
                        api_key=agent_conf.get("api_key"),
                        base_url=agent_conf.get("base_url"),
                        temperature=0.5
                    )
                    data = extract_json(response.get('content', ''))
                    return int(data.get('order_quantity', 0))
                except Exception as e:
                    print(f"AI Error: {e}")
                    return 0

            profit, records = run_inventory_episode(ai_agent_standard, demand_scenarios[i], role_name=f"{model_name} (Standard)")
            for r in records:
                r["Model"] = f"{model_name} (Standard)"
                r["Run"] = i + 1
                all_results.append(r)

    # 3. Run AI Models (CoT + Knowledge)
    for model_name, model_id in MODELS.items():
        print(f"Running {model_name} (CoT + Knowledge)...")
        agent_conf = agents_db.get(model_id)
        
        for i in range(RUNS):
            print(f"  Run {i+1}/{RUNS}")
            
            def ai_agent_cot(state):
                prompt = f"""You are an expert Supply Chain Manager with deep knowledge of Inventory Theory.
Goal: Maximize Total Profit over {PERIODS} periods.

### Knowledge Base:
1. **Base Stock Policy**: The optimal policy for this problem is often a "Base Stock" policy, where you order enough to bring your Inventory Position up to a target level S.
2. **Inventory Position**: Defined as (On-hand Inventory + Pipeline Inventory - Backorders).
3. **Critical Ratio**: The optimal service level is related to the Critical Ratio = Shortage Cost / (Shortage Cost + Holding Cost).
4. **Lead Time Demand**: You must account for demand during the lead time ({LEAD_TIME} periods) plus the review period (1 period).

### Parameters:
- Holding Cost (h): ${HOLDING_COST}/unit/period
- Shortage Penalty (p): ${SHORTAGE_COST}/unit/period
- Ordering Cost: ${ORDERING_COST}/unit
- Selling Price: ${SELLING_PRICE}/unit
- Demand: Normal Distribution (Mean={MEAN_DEMAND}, Std={STD_DEMAND})
- Lead Time (L): {LEAD_TIME} periods.

### Current State (Period {state['period']}):
- On-hand Inventory: {state['inventory']}
- Pipeline (Incoming Orders): {state['pipeline']} (First item arrives next period)

### History:
{chr(10).join(state['history'])}

### Instruction:
You must THINK STEP-BY-STEP before deciding.
1. Calculate the Critical Ratio.
2. Estimate the target Base Stock Level (S) that balances holding and shortage costs.
3. Calculate your current Inventory Position.
4. Determine the Order Quantity = max(0, S - Inventory Position).

Output your reasoning first, then your final decision in JSON.
Reply JSON: {{"order_quantity": integer}}"""

                try:
                    response = ai_chat(
                        messages_or_prompt=[{"role": "user", "content": prompt}],
                        prompt_content=prompt,
                        model=agent_conf.get("model"),
                        api_key=agent_conf.get("api_key"),
                        base_url=agent_conf.get("base_url"),
                        temperature=0.7, # Slightly higher for creative reasoning
                        max_tokens=1024 # Allow more tokens for CoT
                    )
                    data = extract_json(response.get('content', ''))
                    return int(data.get('order_quantity', 0))
                except Exception as e:
                    print(f"AI Error: {e}")
                    return 0

            profit, records = run_inventory_episode(ai_agent_cot, demand_scenarios[i], role_name=f"{model_name} (CoT)")
            for r in records:
                r["Model"] = f"{model_name} (CoT)"
                r["Run"] = i + 1
                all_results.append(r)
    # Save Results
    df = pd.DataFrame(all_results)
    df.to_csv(os.path.join(RESULTS_DIR, "inventory_results.csv"), index=False)
    
    # Plotting
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="Period", y="Inventory_End", hue="Model", style="Run")
    plt.title("Inventory Levels over Time")
    plt.savefig(os.path.join(RESULTS_DIR, "inventory_levels.png"))
    
    plt.figure(figsize=(10, 6))
    # Calculate Cumulative Profit for plot
    sns.lineplot(data=df, x="Period", y="Total_Profit", hue="Model")
    plt.title("Cumulative Profit over Time")
    plt.savefig(os.path.join(RESULTS_DIR, "inventory_profit.png"))
    
    # Summary Stats
    summary = df.groupby(['Model', 'Run'])['Total_Profit'].max().reset_index()
    print("\nSummary Results (Total Profit):")
    print(summary.groupby('Model')['Total_Profit'].mean())

if __name__ == "__main__":
    main()
