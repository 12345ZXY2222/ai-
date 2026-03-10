
import os
import json
import random
import numpy as np
import time
from openai import OpenAI
from scipy.stats import poisson

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
                    {"role": "system", "content": "你是一个乐于助人的助手。你必须输出合法的JSON格式。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            print(f"LLM Error (Attempt {i+1}): {e}")
            time.sleep(2)
    return None

# ==========================================
# Experiment 1: Newsvendor Problem (Zhang et al. 2025)
# ==========================================
class NewsvendorExperiment:
    def __init__(self):
        self.demand_low = 1
        self.demand_high = 300
        self.results = []
        self.prompts_used = {}

    def run_scenario(self, condition_name, price, cost, rounds=5):
        print(f"Running Newsvendor Scenario: {condition_name}")
        critical_ratio = (price - cost) / price
        optimal_q = self.demand_low + critical_ratio * (self.demand_high - self.demand_low)
        
        prompt_template = """
        你是一个管理员，负责管理一种易腐商品的库存。
        
        参数设置：
        - 销售价格 (Price): {price} 元
        - 进货成本 (Cost): {cost} 元
        - 市场需求 (Demand): 在 {low} 到 {high} 之间均匀分布 (Uniform Distribution)。
        
        任务：
        决定你的订货量 (Q)，以最大化期望利润。
        
        参考公式：
        1. 临界比率 (Critical Ratio, CR) = (Price - Cost) / Price
        2. 最优订货量 (Optimal Q) = Low + CR * (High - Low)
        
        请先一步步进行推理计算，然后给出你的决策。
        
        输出 JSON 格式：
        {{
            "reasoning": "你的详细推理过程...",
            "order_quantity": <数字>
        }}
        """
        
        prompt = prompt_template.format(
            price=price, cost=cost, low=self.demand_low, high=self.demand_high
        )
        self.prompts_used[condition_name] = prompt
        
        decisions = []
        reasonings = []
        
        for r in range(rounds):
            res = get_llm_decision(prompt)
            if res:
                q = res.get("order_quantity")
                reasoning = res.get("reasoning", "")
                decisions.append(q)
                reasonings.append(reasoning)
                print(f"  Round {r+1}: Q={q} (Optimal={optimal_q:.2f})")
        
        self.results.append({
            "condition": condition_name,
            "optimal": optimal_q,
            "decisions": decisions,
            "reasonings": reasonings
        })

# ==========================================
# Experiment 2: Beer Game (Full 4-Stage Chain)
# ==========================================
class BeerGameAgent:
    def __init__(self, role, downstream_agent=None, upstream_agent=None):
        self.role = role
        self.downstream = downstream_agent # Who buys from me
        self.upstream = upstream_agent     # Who I buy from
        
        # State
        self.inventory = 12
        self.backlog = 0
        self.incoming_order_queue = [4, 4] # Orders from downstream taking 2 weeks to arrive
        self.incoming_shipment_queue = [4, 4] # Shipments from upstream taking 2 weeks to arrive
        
        # History
        self.order_history = []
        self.inventory_history = []
        self.reasoning_history = []
        
    def receive_shipment(self, amount):
        # Add to shipment queue (delay logic handled in step)
        # Actually, the queue represents the delay. 
        # We append to the end, and pop from the front.
        self.incoming_shipment_queue.append(amount)

    def receive_order(self, amount):
        self.incoming_order_queue.append(amount)

    def step(self, current_week, customer_order=None):
        # 1. Receive Shipment (arriving now)
        arrived_shipment = self.incoming_shipment_queue.pop(0)
        self.inventory += arrived_shipment
        
        # 2. Process Incoming Order (arriving now)
        if self.role == "Retailer":
            current_demand = customer_order
        else:
            current_demand = self.incoming_order_queue.pop(0)
            
        # 3. Fulfill Demand
        to_ship = min(self.inventory, current_demand + self.backlog)
        self.inventory -= to_ship
        self.backlog = (current_demand + self.backlog) - to_ship
        
        # Ship downstream
        if self.downstream:
            self.downstream.receive_shipment(to_ship)
        
        # 4. Decide Order to Upstream
        # Construct Prompt
        # Calculate Pipeline (On Order but not received)
        # For simplicity in prompt, we give them the raw queues
        pipeline = sum(self.incoming_shipment_queue) # In transit to me
        # Note: In real beer game, you also have orders placed but not yet shipped by supplier.
        # But here we simplify "Pipeline" as what is currently in the delay queue.
        
        prompt = f"""
        你是 {self.role}。
        目标：最小化总成本（持有成本 + 缺货成本）。
        
        参数：
        - 持有成本 (Holding Cost): $0.50 /单位/周
        - 缺货成本 (Backlog Cost): $1.00 /单位/周
        - 提前期 (Lead Time): 2周 (你发出的订单需要2周才能到达供应商，供应商发货也需要2周到达你)。
        
        当前状态 (第 {current_week} 周):
        - 本地库存 (Inventory): {self.inventory}
        - 缺货订单 (Backlog): {self.backlog}
        - 本周收到的需求 (Latest Demand): {current_demand}
        - 在途库存 (Incoming Shipments): {self.incoming_shipment_queue} (即将到达)
        
        你的历史订单: {self.order_history[-5:]}
        
        请决定向你的供应商订购多少单位？
        注意：你需要考虑当前的库存、缺货以及在途的货物，以应对未来的需求。
        
        输出 JSON:
        {{
            "reasoning": "分析库存、在途和需求趋势...",
            "order_quantity": <整数>
        }}
        """
        
        res = get_llm_decision(prompt)
        my_order = res.get("order_quantity", 4) if res else 4
        reasoning = res.get("reasoning", "")
        
        self.order_history.append(my_order)
        self.inventory_history.append(self.inventory)
        self.reasoning_history.append(reasoning)
        
        # Send order upstream
        if self.upstream:
            self.upstream.receive_order(my_order)
            
        return prompt # Return prompt for logging

class BeerGameExperiment:
    def __init__(self):
        self.rounds = 15 # 15 weeks
        self.retailer = BeerGameAgent("Retailer")
        self.wholesaler = BeerGameAgent("Wholesaler", downstream_agent=self.retailer)
        self.distributor = BeerGameAgent("Distributor", downstream_agent=self.wholesaler)
        self.factory = BeerGameAgent("Factory", downstream_agent=self.distributor)
        
        # Link upstreams
        self.retailer.upstream = self.wholesaler
        self.wholesaler.upstream = self.distributor
        self.distributor.upstream = self.factory
        self.factory.upstream = None # Factory produces itself
        
        # Factory special logic: Infinite raw materials, but production delay
        # We simulate factory upstream as a "Infinite Source" that receives orders and ships after delay
        # For this implementation, Factory.receive_order adds to its production queue
        # Factory.incoming_shipment_queue acts as production line
        
    def run(self):
        print("Running Full Beer Game Experiment (4 Agents)...")
        prompts = {}
        
        for t in range(1, self.rounds + 1):
            # Demand Step: 4 until week 5, then 8
            customer_demand = 4 if t < 5 else 8
            
            print(f"Week {t} (Demand {customer_demand})...")
            
            # Factory Production Step (Special)
            # Factory "orders" from raw material (infinite), so its "incoming shipment" is just its previous production order
            # We handle Factory logic inside its step, but we need to ensure it gets "shipment" from production
            # Actually, let's just treat Factory.upstream as None, and in step():
            # If upstream is None, we assume we produced what we ordered 2 weeks ago?
            # Let's patch the Factory logic slightly in the loop
            
            # Execute from Upstream to Downstream for Shipments? No, simultaneous.
            # But we need to be careful about order of execution.
            # Standard: Receive Shipments -> Fulfill Demand -> Place Orders.
            
            # 1. Factory Special: "Receive" production (what it ordered 2 weeks ago)
            # Factory's "incoming_shipment_queue" holds production in progress
            
            # Run Agents
            # Note: The order of 'step' doesn't matter much if queues are handled correctly, 
            # but usually we process events.
            
            # Retailer
            p_r = self.retailer.step(t, customer_order=customer_demand)
            
            # Wholesaler
            p_w = self.wholesaler.step(t) # Demand comes from Retailer's order queue
            
            # Distributor
            p_d = self.distributor.step(t)
            
            # Factory
            # Factory needs to "receive" what it put into production. 
            # In `step`, it pops `incoming_shipment_queue`. 
            # When it "orders", it should append to `incoming_shipment_queue` (Production Start).
            # Let's override Factory's upstream behavior here:
            p_f = self.factory.step(t)
            # Factory "Order" = "Start Production". 
            # We manually feed this back into its shipment queue (Production Delay)
            production_order = self.factory.order_history[-1]
            self.factory.incoming_shipment_queue.append(production_order)
            
            if t == 1:
                prompts["Retailer"] = p_r
                
        return {
            "Retailer": {"orders": self.retailer.order_history, "reasoning": self.retailer.reasoning_history},
            "Wholesaler": {"orders": self.wholesaler.order_history, "reasoning": self.wholesaler.reasoning_history},
            "Distributor": {"orders": self.distributor.order_history, "reasoning": self.distributor.reasoning_history},
            "Factory": {"orders": self.factory.order_history, "reasoning": self.factory.reasoning_history},
            "prompts": prompts
        }

# ==========================================
# Experiment 3: Single Echelon (Gijsbrechts 2022)
# ==========================================
class SingleEchelonExperiment:
    def __init__(self):
        self.L = 4
        self.h = 1
        self.p = 9
        self.lam = 5
        self.rounds = 15
        self.prompt_used = ""
        
    def run(self):
        print("Running Single Echelon Experiment...")
        net_inv = 20
        pipeline = [5] * self.L
        
        # Optimal S calculation
        target_S = poisson.ppf(0.9, 5 * (self.L + 1))
        
        history = []
        reasonings = []
        
        for t in range(1, self.rounds + 1):
            demand = np.random.poisson(self.lam)
            
            # 1. Receive
            arrived = pipeline.pop(0)
            net_inv += arrived
            
            # 2. Fulfill
            sales = min(max(0, net_inv), demand)
            net_inv -= sales
            if net_inv < 0: net_inv = 0 # Lost sales
            
            # 3. Decision
            prompt = f"""
            你是一个库存经理，负责管理单一产品（丢失销售模型 Lost Sales Model）。
            目标：最小化总成本。
            
            参数：
            - 持有成本 h = {self.h}
            - 丢失销售惩罚 p = {self.p}
            - 提前期 L = {self.L} 个周期
            - 需求分布 ~ Poisson(lambda={self.lam})
            
            参考公式：
            1. 临界比率 (Critical Ratio) = p / (p + h)
            2. 目标基本库存水平 (Target Base Stock S) = 满足 L+1 个周期需求的临界分位数。
            3. 库存位置 (Inventory Position, IP) = 净库存 + 在途库存。
            4. 订货量 Q = max(0, S - IP)。
            
            当前状态 (第 {t} 周期):
            - 净库存 (Net Inventory): {net_inv}
            - 在途库存 (Pipeline): {pipeline}
            - 当前库存位置 (IP): {net_inv + sum(pipeline)}
            
            任务：
            1. 计算临界比率。
            2. 估算 L+1 个周期的总需求分布。
            3. 确定目标库存水平 S。
            4. 计算订货量 Q。
            
            输出 JSON:
            {{
                "reasoning": "详细的计算和推理过程...",
                "order_quantity": <整数>
            }}
            """
            self.prompt_used = prompt
            
            res = get_llm_decision(prompt)
            order = res.get("order_quantity", 5) if res else 5
            reasoning = res.get("reasoning", "")
            
            pipeline.append(order)
            history.append(order)
            reasonings.append(reasoning)
            
            print(f"  Period {t}: Dem={demand}, NetInv={net_inv}, Order={order}")
            
        return {
            "orders": history, 
            "reasoning": reasonings, 
            "optimal_S": target_S,
            "prompt": self.prompt_used
        }

def main():
    results = {}
    
    # 1. Newsvendor
    nv = NewsvendorExperiment()
    nv.run_scenario("High Profit", price=12, cost=3)
    nv.run_scenario("Low Profit", price=12, cost=9)
    results['newsvendor'] = {
        "data": nv.results,
        "prompts": nv.prompts_used
    }
    
    # 2. Beer Game
    bg = BeerGameExperiment()
    bg_results = bg.run()
    results['beer_game'] = bg_results
    
    # 3. Single Echelon
    se = SingleEchelonExperiment()
    se_results = se.run()
    results['single_echelon'] = se_results
    
    # Save results
    with open("comparison_results_v2.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Experiments completed. Results saved to comparison_results_v2.json")

if __name__ == "__main__":
    main()
