
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

def run_wang_blind_experiment(risk_profile="Risk Neutral"):
    print(f"Running Wang Blind Experiment (No Capacity/SupplyLine Info) - {risk_profile}...")
    
    # Wang: Lead Time = 2 (Total). We use 1 order + 1 ship.
    # NO CAPACITY LIMIT
    factory = BeerGameStage("Factory", None, None, lead_time=1, capacity=None)
    distributor = BeerGameStage("Distributor", factory, None, lead_time=1, capacity=None)
    wholesaler = BeerGameStage("Wholesaler", distributor, None, lead_time=1, capacity=None)
    retailer = BeerGameStage("Retailer", wholesaler, None, lead_time=1, capacity=None)
    
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
            # BLIND EXPERIMENT: Do NOT calculate or show Supply Line
            
            prompt = f"""
            You are a supply chain agent (Role: {stage.name}).
            Current Round: {t}.
            State:
            - Inventory: {stage.inventory}
            - Backlog: {stage.backlog}
            - Incoming Order (Demand): {demands[stage.name]}
            - Lead Time: 2 rounds
            
            Strategy:
            {base_prompt}
            
            Guidelines:
            1. Consider your current inventory, backlog, and expected future orders.
            2. Account for lead time – you need to place orders in advance.
            
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
    data = {}
    
    # Run all 3 profiles
    data["wang_blind_neutral"] = run_wang_blind_experiment("Risk Neutral")
    data["wang_blind_averse"] = run_wang_blind_experiment("Risk Aversion")
    data["wang_blind_seeking"] = run_wang_blind_experiment("Risk Seeking")
    
    with open("wang_blind_results.json", "w") as f:
        json.dump(data, f, indent=4)
        
    print("Blind experiment completed. Results saved to wang_blind_results.json")

if __name__ == "__main__":
    main()
