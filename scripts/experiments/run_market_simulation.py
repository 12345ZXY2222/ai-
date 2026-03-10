import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import seaborn as sns
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
    # Mock
    def ai_chat(**kwargs):
        return {"content": "BUY"}

# --- Configuration ---
RESULTS_DIR = "/home/peirm/ai模拟平台/论文/experiment_results"
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

AGENTS_FILE = "/home/peirm/ai模拟平台/backend/data/agents.json"
def load_agents():
    with open(AGENTS_FILE, 'r') as f:
        return json.load(f)

AGENTS_DB = load_agents()
# Pick a model for LLM agents
LLM_MODEL_ID = "18b70aa2-a723-45be-9766-36f4bcc159a2" # DeepSeek

# --- Parameters ---
NUM_AGENTS = 50
STEPS = 200
SHOCK_TIME = 100
INITIAL_PRICE = 100.0
INITIAL_CASH = 10000.0
INITIAL_STOCKS = 10
LAMBDA_ADJ = 0.01 # Default Price Sensitivity

# Ratios
RATIO_FUNDAMENTAL = 0.3
RATIO_TECHNICAL = 0.3
RATIO_SOCIAL = 0.4

# Network
SMALL_WORLD_K = 4
SMALL_WORLD_P = 0.1

# --- Agent Classes ---

class Trader:
    def __init__(self, id, cash, stocks):
        self.id = id
        self.cash = cash
        self.stocks = stocks
        self.wealth_history = []
        self.type = "Base"
        self.last_action = "HOLD"
        self.last_post = "Just watching the market." # Social post
        
    def update_wealth(self, current_price):
        wealth = self.cash + self.stocks * current_price
        self.wealth_history.append(wealth)
        
    def decide(self, market_state, network_neighbors):
        return 0 # 0: Hold, >0: Buy, <0: Sell

class FundamentalTrader(Trader):
    def __init__(self, id, cash, stocks, noise_level=0.01): # Reduced noise
        super().__init__(id, cash, stocks)
        self.type = "Fundamental"
        self.noise_level = noise_level
        
    def decide(self, market_state, network_neighbors):
        # Estimate value with noise
        true_value = market_state['true_value']
        estimated_value = true_value * (1 + np.random.normal(0, self.noise_level))
        current_price = market_state['price']
        
        if estimated_value > current_price * 1.05: # Increased threshold
            self.last_post = "Price is below value. Good time to buy."
            return 1 # Buy
        elif estimated_value < current_price * 0.95: # Increased threshold
            self.last_post = "Overvalued. I'm selling."
            return -1 # Sell
        self.last_post = "Price seems fair."
        return 0

class TechnicalTrader(Trader):
    def __init__(self, id, cash, stocks, short_window=5, long_window=20):
        super().__init__(id, cash, stocks)
        self.type = "Technical"
        self.short_window = short_window
        self.long_window = long_window
        
    def decide(self, market_state, network_neighbors):
        history = market_state['price_history']
        if len(history) < self.long_window:
            return 0
            
        short_ma = np.mean(history[-self.short_window:])
        long_ma = np.mean(history[-self.long_window:])
        
        if short_ma > long_ma:
            self.last_post = "Upward trend detected! Buying."
            return 1 # Buy
        elif short_ma < long_ma:
            self.last_post = "Downward trend. Selling."
            return -1 # Sell
        self.last_post = "No clear trend."
        return 0

class SocialTrader(Trader):
    def __init__(self, id, cash, stocks, sensitivity=0.5):
        super().__init__(id, cash, stocks)
        self.type = "Social"
        self.sentiment = 0 # -1 to 1
        self.sensitivity = sensitivity
        self.bullish_posts = ["To the moon!", "Buying the dip!", "Everyone is buying!", "Great opportunity!"]
        self.bearish_posts = ["Crash incoming!", "Selling everything!", "Too risky!", "Get out now!"]
        self.neutral_posts = ["Just watching.", "Unsure about direction.", "Holding for now."]
        
    def decide(self, market_state, network_neighbors):
        # 1. Social Influence (Sentiment)
        neighbor_sentiments = [n.sentiment for n in network_neighbors if hasattr(n, 'sentiment')]
        if neighbor_sentiments:
            avg_neighbor_sentiment = np.mean(neighbor_sentiments)
        else:
            avg_neighbor_sentiment = 0
            
        # 2. Price Momentum
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
        
        if self.sentiment > 0.2:
            self.last_post = random.choice(self.bullish_posts)
            return 1
        elif self.sentiment < -0.2:
            self.last_post = random.choice(self.bearish_posts)
            return -1
        self.last_post = random.choice(self.neutral_posts)
        return 0

class LLMSocialTrader(Trader):
    def __init__(self, id, cash, stocks, agent_config, use_cot=False):
        super().__init__(id, cash, stocks)
        self.type = "LLM_Social"
        self.agent_config = agent_config
        self.sentiment = 0
        self.use_cot = use_cot
        
    def decide(self, market_state, network_neighbors):
        # Gather context: Read neighbors' posts!
        neighbor_posts = [f"- {n.last_post}" for n in network_neighbors]
        posts_str = "\n".join(neighbor_posts[:5]) # Limit to 5 posts to save tokens
        
        history_str = ", ".join([f"{p:.1f}" for p in market_state['price_history'][-5:]])
        
        if self.use_cot:
            prompt = f"""You are a Rational Social Trader in a stock market.
Current Price: {market_state['price']:.2f}
Price History (Last 5 days): [{history_str}]

Your Friends' Social Posts:
{posts_str}

Market Rumors: {"A positive rumor about the company's future is spreading." if market_state['shock_active'] else "No major news."}

Financial Theories:
1. Mean Reversion: Prices eventually return to the fundamental value. Rapid spikes often lead to crashes.
2. Herd Behavior: Following the crowd blindly can lead to buying at the peak (Bubble).
3. Momentum: Trends can persist, but be wary of parabolic moves.

Task:
1. Analyze the market trend and your friends' sentiment.
2. THINK STEP-BY-STEP: Is the current price sustainable? Is it a bubble? Should you follow the herd or be contrarian?
3. Write a short social media post (max 10 words).
4. Decide to BUY, SELL, or HOLD.

Reply JSON: {{"thought": "your reasoning", "post": "your post", "action": "BUY/SELL/HOLD"}}"""
        else:
            prompt = f"""You are a Social Trader in a stock market.
Current Price: {market_state['price']:.2f}
Price History (Last 5 days): [{history_str}]

Your Friends' Social Posts:
{posts_str}

Market Rumors: {"A positive rumor about the company's future is spreading." if market_state['shock_active'] else "No major news."}

Task:
1. Analyze the sentiment of your friends and the market trend.
2. Write a short social media post (max 10 words) expressing your view.
3. Decide to BUY, SELL, or HOLD.

Reply JSON: {{"post": "your post", "action": "BUY/SELL/HOLD"}}"""

        try:
            response = ai_chat(
                messages_or_prompt=[{"role": "user", "content": prompt}],
                prompt_content=prompt,
                model=self.agent_config.get("model"),
                api_key=self.agent_config.get("api_key"),
                base_url=self.agent_config.get("base_url"),
                temperature=0.7
            )
            
            # Extract JSON
            content = response.get('content', '')
            match = re.search(r"\{.*?\}", content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                self.last_post = data.get("post", "Watching market.")
                action_str = data.get("action", "HOLD").upper()
            else:
                # Fallback
                self.last_post = "Interesting market."
                action_str = "HOLD"
            
            if "BUY" in action_str:
                self.sentiment = 0.8
                return 1
            elif "SELL" in action_str:
                self.sentiment = -0.8
                return -1
            else:
                self.sentiment = 0
                return 0
        except Exception as e:
            print(f"LLM Error: {e}")
            return 0

# --- Market Simulation ---

def run_market_simulation(use_llm=False, lambda_adj=0.01, version="v2", use_cot=False):
    print(f"Initializing Market Simulation (LLM={use_llm}, Lambda={lambda_adj}, Version={version}, CoT={use_cot})...")
    
    # 1. Create Network
    G = nx.watts_strogatz_graph(NUM_AGENTS, k=SMALL_WORLD_K, p=SMALL_WORLD_P)
    
    # 2. Create Agents
    agents = []
    num_fund = int(NUM_AGENTS * RATIO_FUNDAMENTAL)
    num_tech = int(NUM_AGENTS * RATIO_TECHNICAL)
    num_social = NUM_AGENTS - num_fund - num_tech
    
    # Assign types
    types = ['Fundamental'] * num_fund + ['Technical'] * num_tech + ['Social'] * num_social
    random.shuffle(types)
    
    llm_config = AGENTS_DB.get(LLM_MODEL_ID)
    
    for i in range(NUM_AGENTS):
        atype = types[i]
        if atype == 'Fundamental':
            agent = FundamentalTrader(i, INITIAL_CASH, INITIAL_STOCKS)
        elif atype == 'Technical':
            agent = TechnicalTrader(i, INITIAL_CASH, INITIAL_STOCKS)
        else:
            # If use_llm is True, make half of social traders LLM-based
            if use_llm and i % 2 == 0: 
                agent = LLMSocialTrader(i, INITIAL_CASH, INITIAL_STOCKS, llm_config, use_cot=use_cot)
            else:
                agent = SocialTrader(i, INITIAL_CASH, INITIAL_STOCKS)
        agents.append(agent)
        
    # 3. Simulation Loop
    price = INITIAL_PRICE
    true_value = INITIAL_PRICE
    price_history = [price]
    value_history = [true_value]
    volume_history = []
    post_logs = []
    
    print("Starting Simulation Loop...")
    for t in range(STEPS):
        if t % 20 == 0: print(f"  Step {t}/{STEPS}")
        
        # Update True Value (Random Walk)
        true_value += np.random.normal(0, 0.5)
        
        # Shock
        shock_active = False
        if t == SHOCK_TIME:
            true_value += 10 # Fundamental shock
            print("  !!! SHOCK: True Value Jumped !!!")
        
        # "Rumor" shock (only visible to some, or just price jump)
        # Let's say at t=100, we artificially bump the price to trigger momentum
        if t == SHOCK_TIME:
             price += 5 # Artificial price jump to trigger momentum
             shock_active = True
             
        market_state = {
            'price': price,
            'price_history': price_history,
            'true_value': true_value,
            'shock_active': shock_active
        }
        
        # Collect Orders
        buy_orders = 0
        sell_orders = 0
        
        # Shuffle execution order
        random.shuffle(agents)
        
        agent_actions = {}
        
        for agent in agents:
            neighbors = [agents[n_id] for n_id in list(G.neighbors(agent.id))]
            action = agent.decide(market_state, neighbors)
            
            if action == 1: # Buy
                if agent.cash >= price:
                    buy_orders += 1
                    agent.last_action = "BUY"
            elif action == -1: # Sell
                if agent.stocks > 0:
                    sell_orders += 1
                    agent.last_action = "SELL"
            else:
                agent.last_action = "HOLD"
                
            agent_actions[agent.id] = agent.last_action
            
            # Log Agent State
            post_logs.append({
                'Step': t,
                'AgentID': agent.id,
                'Type': agent.type,
                'Post': getattr(agent, 'last_post', ''),
                'Action': agent.last_action,
                'Cash': agent.cash,
                'Stocks': agent.stocks,
                'Wealth': agent.cash + agent.stocks * price
            })
            
        # Market Clearing (Simplified)
        # Net demand drives price change
        net_demand = buy_orders - sell_orders
        # Price adjustment function: P_new = P_old * (1 + lambda * net_demand)
        # lambda_adj is passed as argument
        new_price = price * (1 + lambda_adj * net_demand)
        new_price = max(0.1, new_price) # Floor
        
        # Execute Trades (Simplified: All orders execute at new price if liquidity allows)
        # In this simple model, we assume infinite liquidity provider for the mismatch
        # Or we just match min(buy, sell). Let's assume Market Maker absorbs.
        
        for agent in agents:
            act = agent_actions[agent.id]
            if act == "BUY" and agent.cash >= new_price:
                agent.cash -= new_price
                agent.stocks += 1
            elif act == "SELL" and agent.stocks > 0:
                agent.cash += new_price
                agent.stocks -= 1
            
            agent.update_wealth(new_price)
            
        price = new_price
        price_history.append(price)
        value_history.append(true_value)
        volume_history.append(buy_orders + sell_orders)
        
    # 4. Analysis & Plotting
    df = pd.DataFrame({
        'Step': range(STEPS + 1),
        'Price': price_history,
        'True_Value': value_history
    })
    
    # Save CSV
    suffix = f"llm_{use_llm}_lambda_{lambda_adj}_{version}_cot_{use_cot}"
    csv_path = os.path.join(RESULTS_DIR, f"market_simulation_{suffix}.csv")
    df.to_csv(csv_path, index=False)
    print(f"Results saved to {csv_path}")
    
    # Save Posts/Logs
    df_posts = pd.DataFrame(post_logs)
    posts_csv_path = os.path.join(RESULTS_DIR, f"market_posts_{suffix}.csv")
    df_posts.to_csv(posts_csv_path, index=False)
    print(f"Detailed logs saved to {posts_csv_path}")
    
    plt.figure(figsize=(12, 6))
    plt.plot(df['Step'], df['Price'], label='Market Price', color='blue')
    plt.plot(df['Step'], df['True_Value'], label='True Value', color='green', linestyle='--')
    plt.axvline(x=SHOCK_TIME, color='red', linestyle=':', label='Shock')
    plt.title(f"Market Bubble Simulation (LLM={use_llm}, Lambda={lambda_adj}, CoT={use_cot})")
    plt.legend()
    plt.savefig(os.path.join(RESULTS_DIR, f"market_bubble_{suffix}.png"))
    
    # Wealth Distribution
    final_wealth = [a.wealth_history[-1] for a in agents]
    agent_types = [a.type for a in agents]
    
    df_wealth = pd.DataFrame({'Wealth': final_wealth, 'Type': agent_types})
    wealth_csv_path = os.path.join(RESULTS_DIR, f"market_wealth_{suffix}.csv")
    df_wealth.to_csv(wealth_csv_path, index=False)
    print(f"Wealth data saved to {wealth_csv_path}")

    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df_wealth, x='Type', y='Wealth')
    plt.title(f"Wealth Distribution (Lambda={lambda_adj}, CoT={use_cot})")
    plt.savefig(os.path.join(RESULTS_DIR, f"market_wealth_{suffix}.png"))
    
    print("Simulation Completed.")
    return df

if __name__ == "__main__":
    # Run with Rule-Based Social Traders first (Fast)
    run_market_simulation(use_llm=False)
    
    # Uncomment to run with LLM (Slow)
    # run_market_simulation(use_llm=True)
