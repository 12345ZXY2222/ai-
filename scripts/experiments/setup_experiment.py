
import json
import uuid
import random
import os

AGENTS_FILE = '/home/peirm/ai模拟平台/backend/data/agents.json'
SIMULATIONS_FILE = '/home/peirm/ai模拟平台/backend/data/simulations.json'

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def create_agents():
    agents = load_json(AGENTS_FILE)
    
    # Find prm's AI_1
    source_agent = None
    for aid, agent in agents.items():
        if agent.get('name') == 'AI_1' and agent.get('user_id') == 'prm':
            source_agent = agent
            break
    
    if not source_agent:
        print("Error: AI_1 for user prm not found.")
        return []

    new_agent_ids = []
    roles = ['Retailer', 'Wholesaler', 'Distributor', 'Manufacturer']
    
    created_agents = {}
    
    for role in roles:
        new_id = str(uuid.uuid4())
        new_agent = source_agent.copy()
        new_agent['id'] = new_id
        new_agent['name'] = f"{role}_prm"
        new_agent['user_id'] = 'prm'
        # We don't set persona here as we'll use prompt_template in simulation
        agents[new_id] = new_agent
        created_agents[role] = new_id
        print(f"Created agent {role}_prm with ID {new_id}")

    save_json(AGENTS_FILE, agents)
    return created_agents

def create_simulation(agent_ids):
    simulations = load_json(SIMULATIONS_FILE)
    
    sim_id = str(uuid.uuid4())
    
    # Risk Neutral Prompt Template
    risk_neutral_prompt = """
You are a Risk Neutral Supply Chain Agent.
You should balance inventory holding costs with the risk of stockouts. Aim to maintain a moderate inventory level that can handle normal demand fluctuations. Try to balance the costs of backlog with the costs of holding excess inventory.

Guidelines for your decision:
1. Consider your current inventory, backlog, and expected future orders.
2. Account for lead time – you need to place orders in advance.
3. Analyze patterns in your downstream’s ordering history to forecast future demand.
4. Try to avoid both stockouts and excess inventory.
5. Open orders should always equal to "expected downstream orders + backlog."

Current Situation:
- Incoming Order from Downstream: {{incoming_order}}
- Your Role: {{role}}

Please first explain your reasoning in 1-2 sentences, then provide your order quantity as a non-negative integer within brackets (e.g. [5]).
"""

    # Steps
    steps = []
    
    # Loop Step
    loop_step_id = str(uuid.uuid4())
    
    inner_steps = []
    
    # 1. Code Step: Generate Demand
    code_step_id = str(uuid.uuid4())
    inner_steps.append({
        "id": code_step_id,
        "type": "code",
        "code_snippet": "import random\nstate['customer_demand'] = str(random.randint(0, 8))",
        "output_var": "customer_demand"
    })
    
    # 2. Retailer Step
    retailer_step_id = str(uuid.uuid4())
    retailer_prompt = risk_neutral_prompt.replace("{{incoming_order}}", "{{state.customer_demand}}").replace("{{role}}", "Retailer")
    inner_steps.append({
        "id": retailer_step_id,
        "type": "agent",
        "agent_ids": [agent_ids['Retailer']],
        "prompt_template": retailer_prompt,
        "output_var": "retailer_order_response"
    })

    # 3. Code Step: Extract Retailer Order (Simple regex or just assume LLM follows format)
    # For simplicity, we'll just pass the whole response to the next agent as "Downstream said..."
    # But the prompt expects a number. Let's try to extract it.
    extract_retailer_code_id = str(uuid.uuid4())
    inner_steps.append({
        "id": extract_retailer_code_id,
        "type": "code",
        "code_snippet": "import re\nmatch = re.search(r'\[(\d+)\]', state['retailer_order_response'])\nstate['retailer_order'] = match.group(1) if match else '4'",
        "output_var": "retailer_order"
    })

    # 4. Wholesaler Step
    wholesaler_step_id = str(uuid.uuid4())
    wholesaler_prompt = risk_neutral_prompt.replace("{{incoming_order}}", "{{state.retailer_order}}").replace("{{role}}", "Wholesaler")
    inner_steps.append({
        "id": wholesaler_step_id,
        "type": "agent",
        "agent_ids": [agent_ids['Wholesaler']],
        "prompt_template": wholesaler_prompt,
        "output_var": "wholesaler_order_response"
    })

    # 5. Code Step: Extract Wholesaler Order
    extract_wholesaler_code_id = str(uuid.uuid4())
    inner_steps.append({
        "id": extract_wholesaler_code_id,
        "type": "code",
        "code_snippet": "import re\nmatch = re.search(r'\[(\d+)\]', state['wholesaler_order_response'])\nstate['wholesaler_order'] = match.group(1) if match else '4'",
        "output_var": "wholesaler_order"
    })

    # 6. Distributor Step
    distributor_step_id = str(uuid.uuid4())
    distributor_prompt = risk_neutral_prompt.replace("{{incoming_order}}", "{{state.wholesaler_order}}").replace("{{role}}", "Distributor")
    inner_steps.append({
        "id": distributor_step_id,
        "type": "agent",
        "agent_ids": [agent_ids['Distributor']],
        "prompt_template": distributor_prompt,
        "output_var": "distributor_order_response"
    })

    # 7. Code Step: Extract Distributor Order
    extract_distributor_code_id = str(uuid.uuid4())
    inner_steps.append({
        "id": extract_distributor_code_id,
        "type": "code",
        "code_snippet": "import re\nmatch = re.search(r'\[(\d+)\]', state['distributor_order_response'])\nstate['distributor_order'] = match.group(1) if match else '4'",
        "output_var": "distributor_order"
    })

    # 8. Manufacturer Step
    manufacturer_step_id = str(uuid.uuid4())
    manufacturer_prompt = risk_neutral_prompt.replace("{{incoming_order}}", "{{state.distributor_order}}").replace("{{role}}", "Manufacturer")
    inner_steps.append({
        "id": manufacturer_step_id,
        "type": "agent",
        "agent_ids": [agent_ids['Manufacturer']],
        "prompt_template": manufacturer_prompt,
        "output_var": "manufacturer_order_response"
    })

    loop_step = {
        "id": loop_step_id,
        "type": "loop",
        "repeat_count": 10,
        "inner_steps": inner_steps,
        "agent_ids": [],
        "files": []
    }
    
    steps.append(loop_step)
    
    new_simulation = {
        "id": sim_id,
        "name": "Beer Game - Risk Neutral (Paper Reproduction)",
        "description": "Reproduction of the Beer Game experiment from 'LLMs for Supply Chain Management' with Risk Neutral agents.",
        "steps": steps,
        "variables": [
            {"key": "customer_demand", "value": "0", "description": "Current customer demand"},
            {"key": "retailer_order", "value": "0", "description": "Order from Retailer"},
            {"key": "wholesaler_order", "value": "0", "description": "Order from Wholesaler"},
            {"key": "distributor_order", "value": "0", "description": "Order from Distributor"},
            {"key": "retailer_order_response", "value": "", "description": "Raw response"},
            {"key": "wholesaler_order_response", "value": "", "description": "Raw response"},
            {"key": "distributor_order_response", "value": "", "description": "Raw response"},
            {"key": "manufacturer_order_response", "value": "", "description": "Raw response"}
        ],
        "user_id": "prm"
    }
    
    simulations[sim_id] = new_simulation
    save_json(SIMULATIONS_FILE, simulations)
    print(f"Created simulation with ID {sim_id}")

if __name__ == "__main__":
    agent_ids = create_agents()
    if agent_ids:
        create_simulation(agent_ids)

