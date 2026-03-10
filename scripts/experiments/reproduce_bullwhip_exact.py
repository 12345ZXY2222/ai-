
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
                    {"role": "system", "content": "You are a helpful assistant. Output valid JSON."},
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
    return {"quantity": 0} # Fallback

class BeerGameStage:
    def __init__(self, name, upstream, downstream, lead_time, initial_inv=12, capacity=None):
        self.name = name
        self.upstream = upstream
        self.downstream = downstream
        
        # State
        self.inventory = initial_inv
        self.backlog = 0
        self.incoming_order = 0 # Order received from downstream
        self.outgoing_order = 0 # Order placed to upstream
        self.incoming_shipment = 0 # Shipment received from upstream
        self.outgoing_shipment = 0 # Shipment sent to downstream
        
        # Delays
        # We model delay as a queue. 
        # Incoming Shipment Delay: From Upstream to Me.
        # Incoming Order Delay: From Downstream to Me.
        # Sterman: 2 weeks mail (order), 2 weeks shipping.
        # Wang: "Lead Time 2". We'll assume 1 week order, 1 week ship? Or 2 week ship.
        # Let's make it configurable.
        self.shipment_queue = [4] * lead_time # Initial pipeline
        self.order_queue = [4] * lead_time    # Initial order pipeline
        
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
        # 1. Receive Shipment (Pop from queue)
        arrived = self.shipment_queue.pop(0)
        self.inventory += arrived
        
        # 2. Receive Order (Pop from queue)
        # For Retailer, this is customer demand (immediate).
        # For others, it comes from downstream's delay.
        if self.downstream is None: # Retailer
            current_demand = self.incoming_order # Set externally
        else:
            current_demand = self.order_queue.pop(0)
            
        self.history["demand"].append(current_demand)
            
        # 3. Fulfill Demand
        # Total demand = Current + Backlog
        total_req = current_demand + self.backlog
        to_ship = min(self.inventory, total_req)
        
        # Capacity constraint (Wang)
        if self.capacity is not None:
            to_ship = min(to_ship, self.capacity)
            
        self.inventory -= to_ship
        self.backlog = total_req - to_ship
        self.outgoing_shipment = to_ship
        
        # Ship to downstream
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
            # Factory: Orders from "Raw Materials" (Infinite)
            # We simulate this by adding to our own shipment queue (Production Delay)
            # But wait, receive_shipment appends to queue.
            # So Factory ordering X means X enters the queue to arrive later.
            self.receive_shipment(quantity)

# ==========================================
# 1. Sterman (1989) Reproduction
# ==========================================
class StermanAgent:
    def __init__(self, alpha=0.26, beta=0.26, theta=0.26):
        self.alpha = alpha
        self.beta = beta
        self.theta = theta
        self.S_star = 12 # Desired Stock
        self.SL_star = 8 # Desired Supply Line (Expected demand 4 * Lead time 2?)
        # Sterman estimated S' = 28 approx? Let's use the formula.
        # Rule: O_t = Forecast_t + alpha(S* - S_t) + beta(SL* - SL_t)
        # Forecast_t = theta * Demand_t + (1-theta) * Forecast_{t-1}
        self.forecast = 4.0
        
    def decide(self, inventory, backlog, supply_line, current_demand):
        # Update Forecast (Adaptive Expectations)
        self.forecast = self.theta * current_demand + (1 - self.theta) * self.forecast
        
        # Desired Supply Line: Coverage of Lead Time * Forecast
        # Lead Time = 4 (2 mail + 2 ship)
        desired_sl = 4 * self.forecast 
        
        # Desired Stock: Coverage of expected demand? 
        # Sterman subjects often anchored to 12.
        desired_s = 12 
        
        # Adjustments
        stock_adj = self.alpha * (desired_s - (inventory - backlog))
        line_adj = self.beta * (desired_sl - supply_line)
        
        order = self.forecast + stock_adj + line_adj
        return max(0, int(order))

def run_sterman_experiment():
    print("Running Sterman (1989) Reproduction...")
    # Setup: 4 Stages, L=2 (Mail) + 2 (Ship) = 4 total delay?
    # Sterman's board: "Mail Delay" (2 slots) + "Shipping Delay" (2 slots).
    # So Stage Lead Time = 2 (Ship) + 2 (Order) = 4.
    
    stages = ["Retailer", "Wholesaler", "Distributor", "Factory"]
    agents = {name: StermanAgent() for name in stages}
    
    # Linkages
    # Note: In our class, 'lead_time' is the length of the queue.
    # If we want 2 weeks mail + 2 weeks ship:
    # Downstream places order -> Order Queue (2) -> Upstream receives.
    # Upstream ships -> Shipment Queue (2) -> Downstream receives.
    # So we set lead_time=2 for both queues in the class.
    
    factory = BeerGameStage("Factory", None, None, lead_time=2)
    distributor = BeerGameStage("Distributor", factory, None, lead_time=2)
    wholesaler = BeerGameStage("Wholesaler", distributor, None, lead_time=2)
    retailer = BeerGameStage("Retailer", wholesaler, None, lead_time=2)
    
    # Link Downstream
    factory.downstream = distributor
    distributor.downstream = wholesaler
    wholesaler.downstream = retailer
    retailer.downstream = None # Customer
    
    # Link Upstream
    retailer.upstream = wholesaler
    wholesaler.upstream = distributor
    distributor.upstream = factory
    factory.upstream = None
    
    chain = [retailer, wholesaler, distributor, factory]
    
    results = {name: [] for name in stages}
    
    # Run 36 weeks
    for t in range(1, 37):
        # Demand: Step 4 -> 8 at week 5
        demand = 4 if t < 5 else 8
        
        # 1. Logistics Step (Receive & Ship)
        retailer.incoming_order = demand
        
        # Execute from Upstream to Downstream? 
        # In Beer Game, usually simultaneous.
        # We run logistics for all first.
        demands = {}
        for stage in chain:
            demands[stage.name] = stage.step_logistics()
            
        # 2. Decision Step
        for stage in chain:
            # Calculate Supply Line: Sum of Order Queue + Shipment Queue?
            # Supply Line = Orders placed but not yet received.
            # = My Incoming Shipment Queue + Upstream's Order Queue + Upstream's Backlog?
            # Simplified: Total Pipeline.
            # For Sterman Agent, Supply Line is what they *perceive*.
            # Usually sum of all on-order.
            pipeline = sum(stage.shipment_queue) 
            # Note: In real game, you don't see upstream's order queue.
            # But you know what you ordered.
            # Supply Line = Total Orders Placed - Total Shipments Received.
            # We can track this or just sum the queues if we have perfect info.
            # Sterman agents usually estimate it.
            # Let's use sum(shipment_queue) + sum(upstream.order_queue) if accessible?
            # No, let's use a simplified proxy: 4 weeks worth of recent orders?
            # Or just sum(stage.shipment_queue) + sum(stage.upstream.order_queue) if we assume they know what they ordered.
            # Actually, Supply Line = Cumulative Orders - Cumulative Arrivals.
            
            # Let's just use the queues we have.
            # If I am Retailer, my Supply Line is:
            # Items in Wholesaler's Order Queue (from me) + Items in Wholesaler's Backlog (for me) + Items in My Shipment Queue.
            sl = sum(stage.shipment_queue)
            if stage.upstream:
                sl += sum(stage.upstream.order_queue) + stage.upstream.backlog
            else:
                # Factory supply line is just production delay
                sl += sum(stage.shipment_queue) # Double count? No. Factory orders into its own shipment queue.
                
            agent = agents[stage.name]
            qty = agent.decide(stage.inventory, stage.backlog, sl, demands[stage.name])
            stage.place_order(qty)
            results[stage.name].append(qty)
            
    return results

# ==========================================
# 2. Wang et al. (2025) Reproduction
# ==========================================
def run_wang_experiment():
    print("Running Wang et al. (2025) Reproduction...")
    # Setup: 4 Stages.
    # Lead Time: 2 (Total). 
    # We can split this: 1 week order delay, 1 week ship delay.
    # Or 0 week order delay, 2 week ship delay.
    # Wang prompt says "Lead Time: 2 round(s)".
    # Let's use 1 and 1.
    
    factory = BeerGameStage("Factory", None, None, lead_time=1, capacity=20)
    distributor = BeerGameStage("Distributor", factory, None, lead_time=1, capacity=20)
    wholesaler = BeerGameStage("Wholesaler", distributor, None, lead_time=1, capacity=20)
    retailer = BeerGameStage("Retailer", wholesaler, None, lead_time=1, capacity=20)
    
    # Link
    factory.downstream = distributor
    distributor.downstream = wholesaler
    wholesaler.downstream = retailer
    
    retailer.upstream = wholesaler
    wholesaler.upstream = distributor
    distributor.upstream = factory
    
    chain = [retailer, wholesaler, distributor, factory]
    results = {name: [] for name in ["Retailer", "Wholesaler", "Distributor", "Factory"]}
    
    # Run 12 periods (Wang Table I says 12 periods? That's very short for Bullwhip).
    # Page 16 Table I: "Number of Periods 12".
    # But Page 26 says "Over 24 periods".
    # I will use 24 periods to allow dynamics to show.
    rounds = 24
    
    for t in range(1, rounds + 1):
        # Demand: U[0, 8]
        demand = np.random.randint(0, 9)
        print(f"Round {t}, Demand {demand}")
        
        # 1. Logistics
        retailer.incoming_order = demand
        demands = {}
        for stage in chain:
            demands[stage.name] = stage.step_logistics()
            
        # 2. Decision (LLM)
        for stage in chain:
            # Construct Prompt
            # Wang Prompt (Risk Neutral)
            prompt = f"""
            You are a supply chain agent (Role: {stage.name}).
            Current Round: {t}.
            State:
            - Inventory: {stage.inventory}
            - Backlog: {stage.backlog}
            - Incoming Order (Demand): {demands[stage.name]}
            - Lead Time: 2 rounds
            
            Risk Neutral Strategy:
            You should balance inventory holding costs ($0.5) with the risk of stockouts ($1.0). 
            Aim to maintain a moderate inventory level that can handle normal demand fluctuations.
            
            Please analyze the market situation, then provide your quantity decision. 
            Start by explaining your reasoning in one or two sentences, then give an integer quantity in JSON format.
            Example: {{"reasoning": "...", "quantity": 5}}
            """
            
            res = get_llm_decision(prompt)
            qty = res.get("quantity", 4)
            stage.place_order(qty)
            results[stage.name].append(qty)
            
    return results

def main():
    sterman_data = run_sterman_experiment()
    wang_data = run_wang_experiment()
    
    final_data = {
        "sterman": sterman_data,
        "wang": wang_data
    }
    
    with open("bullwhip_reproduction_data.json", "w") as f:
        json.dump(final_data, f)
    print("Done.")

if __name__ == "__main__":
    main()
