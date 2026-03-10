
import numpy as np
import json
import os
import time
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv("backend/.env")

# Configuration
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
BASE_URL = "https://api.deepseek.com"
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def get_llm_decision(prompt, model="deepseek-chat", temperature=0.1):
    retries = 3
    for i in range(retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a supply chain agent. Output valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            print(f"LLM Error: {e}")
            time.sleep(1)
    return {"quantity": 4} # Fallback

class BeerGameStage:
    def __init__(self, name, upstream, downstream, lead_time, initial_inv=12, capacity=None):
        self.name = name
        self.upstream = upstream
        self.downstream = downstream
        
        # State
        self.inventory = initial_inv
        self.backlog = 0
        self.incoming_order = 0 
        self.outgoing_order = 0 
        self.incoming_shipment = 0 
        self.outgoing_shipment = 0 
        
        # Delays (Queues)
        # Wang: Lead Time = 2. 
        # We assume this means 2 periods from Order Placement to Receipt?
        # Or 2 periods of shipping delay?
        # Let's assume 1 period order delay + 1 period ship delay = 2 total.
        self.shipment_queue = [4] * lead_time 
        self.order_queue = [4] * lead_time    
        
        self.capacity = capacity
        
        # History
        self.history = {
            "inventory": [],
            "backlog": [],
            "orders": [],
            "demand": []
        }

    def receive_order(self, amount):
        self.order_queue.append(amount)
        
    def receive_shipment(self, amount):
        self.shipment_queue.append(amount)

    def step_logistics(self):
        # 1. Receive Shipment
        arrived = self.shipment_queue.pop(0)
        self.inventory += arrived
        
        # 2. Receive Order
        if self.downstream is None: # Retailer
            current_demand = self.incoming_order
        else:
            current_demand = self.order_queue.pop(0)
            
        self.history["demand"].append(current_demand)
            
        # 3. Fulfill Demand
        total_req = current_demand + self.backlog
        to_ship = min(self.inventory, total_req)
        
        if self.capacity is not None:
            to_ship = min(to_ship, self.capacity)
            
        self.inventory -= to_ship
        self.backlog = total_req - to_ship
        self.outgoing_shipment = to_ship
        
        if self.downstream:
            self.downstream.receive_shipment(to_ship)
            
        return current_demand

    def place_order(self, quantity):
        self.outgoing_order = quantity
        self.history["orders"].append(quantity)
        self.history["inventory"].append(self.inventory)
        self.history["backlog"].append(self.backlog)
        
        if self.upstream:
            self.upstream.receive_order(quantity)
        else:
            # Factory orders from infinite source
            self.receive_shipment(quantity)

# ==========================================
# 1. Sterman (1989) Reproduction
# ==========================================
class StermanAgent:
    def __init__(self, alpha=0.26, beta=0.26, theta=0.26):
        self.alpha = alpha
        self.beta = beta
        self.theta = theta
        self.S_star = 12 
        self.SL_star = 8 
        self.forecast = 4.0
        
    def decide(self, inventory, backlog, supply_line, current_demand):
        self.forecast = self.theta * current_demand + (1 - self.theta) * self.forecast
        desired_sl = 4 * self.forecast 
        desired_s = 12 
        stock_adj = self.alpha * (desired_s - (inventory - backlog))
        line_adj = self.beta * (desired_sl - supply_line)
        order = self.forecast + stock_adj + line_adj
        return max(0, int(order))

def run_sterman_experiment():
    print("Running Sterman (1989) Reproduction...")
    stages = ["Retailer", "Wholesaler", "Distributor", "Factory"]
    agents = {name: StermanAgent() for name in stages}
    
    # Sterman: 2 weeks mail + 2 weeks ship = 4 weeks total delay per stage
    # We use lead_time=2 for both queues (order & ship)
    factory = BeerGameStage("Factory", None, None, lead_time=2)
    distributor = BeerGameStage("Distributor", factory, None, lead_time=2)
    wholesaler = BeerGameStage("Wholesaler", distributor, None, lead_time=2)
    retailer = BeerGameStage("Retailer", wholesaler, None, lead_time=2)
    
    factory.downstream = distributor
    distributor.downstream = wholesaler
    wholesaler.downstream = retailer
    
    retailer.upstream = wholesaler
    wholesaler.upstream = distributor
    distributor.upstream = factory
    
    chain = [retailer, wholesaler, distributor, factory]
    results = {name: {"orders": [], "inventory": [], "backlog": []} for name in stages}
    
    # Run 36 weeks (Sterman standard)
    for t in range(1, 37):
        demand = 4 if t < 5 else 8
        retailer.incoming_order = demand
        
        demands = {}
        for stage in chain:
            demands[stage.name] = stage.step_logistics()
            
        for stage in chain:
            sl = sum(stage.shipment_queue)
            if stage.upstream:
                sl += sum(stage.upstream.order_queue) + stage.upstream.backlog
            else:
                sl += sum(stage.shipment_queue)
                
            agent = agents[stage.name]
            qty = agent.decide(stage.inventory, stage.backlog, sl, demands[stage.name])
            stage.place_order(qty)
            results[stage.name]["orders"].append(qty)
            results[stage.name]["inventory"].append(stage.inventory)
            results[stage.name]["backlog"].append(stage.backlog)
            
    return results

# ==========================================
# 2. Wang et al. (2025) Reproduction
# ==========================================
def run_wang_experiment(risk_profile="Risk Neutral"):
    print(f"Running Wang et al. (2025) Reproduction - {risk_profile}...")
    
    # Wang: Lead Time = 2 (Total). We use 1 order + 1 ship.
    factory = BeerGameStage("Factory", None, None, lead_time=1, capacity=20)
    distributor = BeerGameStage("Distributor", factory, None, lead_time=1, capacity=20)
    wholesaler = BeerGameStage("Wholesaler", distributor, None, lead_time=1, capacity=20)
    retailer = BeerGameStage("Retailer", wholesaler, None, lead_time=1, capacity=20)
    
    factory.downstream = distributor
    distributor.downstream = wholesaler
    wholesaler.downstream = retailer
    
    retailer.upstream = wholesaler
    wholesaler.upstream = distributor
    distributor.upstream = factory
    
    chain = [retailer, wholesaler, distributor, factory]
    results = {name: {"orders": [], "inventory": [], "backlog": []} for name in ["Retailer", "Wholesaler", "Distributor", "Factory"]}
    
    # Prompts
    prompts = {
        "Risk Aversion": """
        You are highly risk-averse and prioritize avoiding stockouts at all costs. You should maintain
        higher inventory levels to ensure you can always meet demand. It’s better to have excess
        inventory than to risk backlog. You should place larger orders earlier to provide a safety
        buffer.
        """,
        "Risk Neutral": """
        You should balance inventory holding costs with the risk of stockouts. Aim to maintain a
        moderate inventory level that can handle normal demand fluctuations. Try to balance the
        costs of backlog with the costs of holding excess inventory.
        """,
        "Risk Seeking": """
        You are profit-oriented, and your first goal is to obtain the highest reward. You should keep
        inventory levels low and place orders in a timely manner. If the loss caused by backlogs
        affects your reward, you should replenish the stock in time. You should place orders more
        frequently and adjust your ordering strategy in time to ensure higher rewards.
        """
    }
    
    base_prompt = prompts.get(risk_profile, prompts["Risk Neutral"])
    
    # Run 24 periods (Wang)
    rounds = 24
    
    for t in range(1, rounds + 1):
        # Demand: U[0, 8]
        demand = np.random.randint(0, 9)
        
        retailer.incoming_order = demand
        demands = {}
        for stage in chain:
            demands[stage.name] = stage.step_logistics()
            
        for stage in chain:
            # Calculate Supply Line (Total ordered but not received)
            # = Sum of upstream's order queue (if any) + upstream's backlog + shipment queue
            supply_line = sum(stage.shipment_queue)
            if stage.upstream:
                supply_line += sum(stage.upstream.order_queue) + stage.upstream.backlog
            else:
                # Factory: Infinite supply, so supply line is just what's in shipment queue (transit)
                # But wait, Factory places order to "Infinite Source".
                # In my code, Factory.place_order calls receive_shipment immediately?
                # No, place_order -> upstream.receive_order.
                # If upstream is None (Factory), it calls self.receive_shipment(quantity).
                # receive_shipment appends to shipment_queue.
                # So Factory supply line is just shipment_queue.
                pass

            prompt = f"""
            You are a supply chain agent (Role: {stage.name}).
            Current Round: {t}.
            State:
            - Inventory: {stage.inventory}
            - Backlog: {stage.backlog}
            - Incoming Order (Demand): {demands[stage.name]}
            - Total Pending Orders (Placed but not received): {supply_line}
            - Lead Time: 2 rounds
            - Production/Shipping Capacity: 20 units per round
            
            Strategy:
            {base_prompt}
            
            Guidelines:
            1. Consider your current inventory, backlog, and expected future orders.
            2. Account for lead time – you need to place orders in advance.
            3. CRITICAL: Do not double-order! Check 'Total Pending Orders' before placing new orders.
            4. Note the capacity limit (20). Ordering more than 20 will just increase backlog if you are the supplier, or won't arrive faster if you are the buyer.
            
            Please analyze the market situation, then provide your quantity decision. 
            Start by explaining your reasoning in one or two sentences, then give an integer quantity in JSON format.
            Example: {{"reasoning": "...", "quantity": 5}}
            """
            
            res = get_llm_decision(prompt)
            qty = res.get("quantity", 4)
            stage.place_order(qty)
            results[stage.name]["orders"].append(qty)
            results[stage.name]["inventory"].append(stage.inventory)
            results[stage.name]["backlog"].append(stage.backlog)
            
    return results

def main():
    # 1. Sterman
    sterman_data = run_sterman_experiment()
    
    # 2. Wang - 3 Profiles
    wang_neutral = run_wang_experiment("Risk Neutral")
    wang_averse = run_wang_experiment("Risk Aversion")
    wang_seeking = run_wang_experiment("Risk Seeking")
    
    final_data = {
        "sterman": sterman_data,
        "wang_neutral": wang_neutral,
        "wang_averse": wang_averse,
        "wang_seeking": wang_seeking
    }
    
    with open("bullwhip_reproduction_full.json", "w") as f:
        json.dump(final_data, f)
    print("Full reproduction completed.")

if __name__ == "__main__":
    main()
