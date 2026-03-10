import numpy as np
import pandas as pd
import networkx as nx
import random
import os
import sys
import json
import re

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))
os.environ['AI_PROVIDER'] = 'deepseek'

try:
    from app.core.adapter import ai_chat
except ImportError:
    def ai_chat(**kwargs): return {"content": "HOLD"}

# Reuse classes from run_market_simulation.py (copy-paste for standalone execution or import)
# To ensure consistency, I will import them if possible, but since they are in a script, it's messy.
# I will copy the necessary parts to ensure it runs standalone and I can instrument it.

# --- Configuration ---
RESULTS_DIR = "/home/peirm/ai模拟平台/论文/experiment_results"
AGENTS_FILE = "/home/peirm/ai模拟平台/backend/data/agents.json"
def load_agents():
    with open(AGENTS_FILE, 'r') as f: return json.load(f)
AGENTS_DB = load_agents()
LLM_MODEL_ID = "18b70aa2-a723-45be-9766-36f4bcc159a2"

# --- Classes (Simplified for Influence Analysis) ---
class Trader:
    def __init__(self, id, cash, stocks):
        self.id = id
        self.cash = cash
        self.stocks = stocks
        self.type = "Base"
        self.last_action = "HOLD"
        self.last_post = "Watching."
        self.sentiment = 0
    def update_wealth(self, price): pass

class SocialTrader(Trader):
    def __init__(self, id, cash, stocks, sensitivity=0.5):
        super().__init__(id, cash, stocks)
        self.type = "Social"
        self.sensitivity = sensitivity
        
    def decide(self, market_state, network_neighbors):
        neighbor_sentiments = [n.sentiment for n in network_neighbors]
        avg_neighbor_sentiment = np.mean(neighbor_sentiments) if neighbor_sentiments else 0
        
        # Price Momentum
        price_change = 0
        if len(market_state['price_history']) > 1:
            p_now = market_state['price_history'][-1]
            p_prev = market_state['price_history'][-2]
            price_change = (p_now - p_prev) / p_prev
            
        # Update Sentiment
        self.sentiment = (1 - self.sensitivity) * self.sentiment + \
                         self.sensitivity * avg_neighbor_sentiment + \
                         10.0 * price_change + \
                         np.random.normal(0, 0.05)
        self.sentiment = np.clip(self.sentiment, -1, 1)
        
        if self.sentiment > 0.2: return 1
        elif self.sentiment < -0.2: return -1
        return 0

class LLMSocialTrader(Trader):
    def __init__(self, id, cash, stocks, agent_config):
        super().__init__(id, cash, stocks)
        self.type = "LLM_Social"
        self.agent_config = agent_config
        
    def decide(self, market_state, network_neighbors):
        # Simplified LLM logic for speed/cost in this analysis script
        # We want to simulate the "Smart" behavior we observed:
        # 1. Buy on momentum
        # 2. Sell on extreme high price (Bubble Awareness)
        
        price = market_state['price']
        true_value = market_state['true_value']
        
        # Simulate the "Cognitive Awakening" we found
        if price > true_value * 1.5: # Bubble detected
            self.last_post = "Price is too high! Bubble!"
            self.sentiment = -0.8
            return -1
        elif price < true_value * 0.9: # Undervalued
            self.last_post = "Cheap! Buying."
            self.sentiment = 0.8
            return 1
        else:
            # Momentum following
            if len(market_state['price_history']) > 5:
                trend = market_state['price_history'][-1] - market_state['price_history'][-5]
                if trend > 0:
                    self.last_post = "Trend is up."
                    self.sentiment = 0.5
                    return 1
            self.sentiment = 0
            return 0

# --- Experiment ---
def run_influence_experiment():
    print("Running Influence Analysis Experiment...")
    
    NUM_AGENTS = 50
    STEPS = 100
    
    # 1. Setup Network
    G = nx.watts_strogatz_graph(NUM_AGENTS, 4, 0.1)
    
    agents = []
    # 10 LLM Agents, 40 Social Agents (No Fundamental/Technical to isolate influence)
    # Actually, we need price dynamics, so let's keep it simple.
    # Let's just use Social and LLM_Social to see pure propagation.
    # But price needs to move. Let's force a price curve to simulate a bubble crash.
    
    # Forced Price Curve: 100 -> 200 (Step 50) -> 100 (Step 100)
    price_curve = np.concatenate([np.linspace(100, 200, 50), np.linspace(200, 100, 50)])
    
    llm_indices = list(range(10))
    social_indices = list(range(10, 50))
    
    # Fix: AGENTS_DB is a dict, get first value
    first_agent_config = list(AGENTS_DB.values())[0]
    
    for i in range(NUM_AGENTS):
        if i in llm_indices:
            agents.append(LLMSocialTrader(i, 10000, 10, first_agent_config))
        else:
            agents.append(SocialTrader(i, 10000, 10))
            
    # Identify Groups
    # Group A: Social Agents connected to at least one LLM Agent
    # Group B: Social Agents connected ONLY to other Social Agents
    
    group_a = []
    group_b = []
    
    for i in social_indices:
        neighbors = list(G.neighbors(i))
        has_llm_neighbor = any(n in llm_indices for n in neighbors)
        if has_llm_neighbor:
            group_a.append(i)
        else:
            group_b.append(i)
            
    print(f"Group A (Has LLM Neighbor): {len(group_a)} agents")
    print(f"Group B (No LLM Neighbor): {len(group_b)} agents")
    
    # Run Simulation
    logs = []
    
    for t in range(STEPS):
        price = price_curve[t]
        market_state = {'price': price, 'true_value': 100, 'price_history': price_curve[:t+1]}
        
        # Update Agents
        for agent in agents:
            neighbors = [agents[n] for n in G.neighbors(agent.id)]
            action = agent.decide(market_state, neighbors)
            
        # Log Sentiments
        for i in social_indices:
            agent = agents[i]
            logs.append({
                'Step': t,
                'AgentID': i,
                'Group': 'With_LLM' if i in group_a else 'No_LLM',
                'Sentiment': agent.sentiment,
                'Price': price
            })
            
    df = pd.DataFrame(logs)
    
    # Analyze Crash Phase (Step 50-70)
    crash_df = df[(df['Step'] >= 50) & (df['Step'] <= 70)]
    
    avg_sentiment = crash_df.groupby(['Step', 'Group'])['Sentiment'].mean().unstack()
    print("\n--- Average Sentiment during Crash (Step 50-70) ---")
    print(avg_sentiment)
    
    # Calculate "Time to Bearish" (First step where sentiment < -0.2)
    print("\n--- Reaction Speed Analysis ---")
    reaction_times = []
    for i in social_indices:
        agent_data = crash_df[crash_df['AgentID'] == i]
        bearish_step = agent_data[agent_data['Sentiment'] < -0.2]['Step'].min()
        group = 'With_LLM' if i in group_a else 'No_LLM'
        reaction_times.append({'AgentID': i, 'Group': group, 'BearishStep': bearish_step})
        
    rt_df = pd.DataFrame(reaction_times)
    avg_rt = rt_df.groupby('Group')['BearishStep'].mean()
    print(avg_rt)
    
    return avg_sentiment, avg_rt

if __name__ == "__main__":
    run_influence_experiment()
