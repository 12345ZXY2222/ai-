import json
import uuid
import os

# Define file path
SIMULATIONS_FILE = "/home/peirm/ai模拟平台/backend/data/simulations.json"

# Load existing simulations
if os.path.exists(SIMULATIONS_FILE):
    with open(SIMULATIONS_FILE, "r") as f:
        simulations_db = json.load(f)
else:
    simulations_db = {}

# --- Helper to create a step ---
def create_agent_step(agent_id, prompt, output_var):
    return {
        "id": str(uuid.uuid4()),
        "type": "agent",
        "agent_ids": [agent_id],
        "prompt_template": prompt,
        "output_var": output_var,
        "files": []
    }

def create_code_step(code):
    return {
        "id": str(uuid.uuid4()),
        "type": "code",
        "code_snippet": code,
        "files": []
    }

# --- Define Agents (Placeholders, user needs to create actual agents or we use generic IDs) ---
# For this script, we'll assume the user will map these IDs to real agents later, 
# or we can use the IDs from the existing DB if we knew them. 
# Let's use placeholders "agent-proposer" and "agent-responder".
# In a real scenario, the user would select specific agents from the UI.
PROPOSER_ID = "agent-proposer-placeholder" 
RESPONDER_ID = "agent-responder-placeholder"

# --- Simulation 1: Ultimatum Game (Baseline - Neutral) ---
sim_baseline_id = str(uuid.uuid4())
sim_baseline = {
    "id": sim_baseline_id,
    "name": "Ultimatum Game - Baseline (Neutral)",
    "description": "Standard Ultimatum Game with neutral economic framing. Proposer offers a split of 100 coins.",
    "variables": [
        {"key": "total_amount", "value": "100"},
        {"key": "offer", "value": "0"},
        {"key": "decision", "value": ""}
    ],
    "steps": [
        # Step 1: Proposer makes an offer
        create_agent_step(
            PROPOSER_ID,
            """You are Participant A in an economic experiment. 
You have been endowed with {{state.total_amount}} coins. 
You must propose a division of this amount between yourself and Participant B.
If Participant B accepts your proposal, you both receive the amounts you proposed.
If Participant B rejects your proposal, you both receive 0 coins.

How many coins do you offer to Participant B?
Reply with ONLY a JSON object: {"offer": integer}""",
            "proposer_output"
        ),
        # Step 2: Extract offer (Code)
        create_code_step(
            """
data = extract_json(state['proposer_output'])
if data and 'offer' in data:
    state['offer'] = int(data['offer'])
else:
    state['offer'] = 0 # Default fallback
print(f"Proposer offered: {state['offer']}")
"""
        ),
        # Step 3: Responder decides
        create_agent_step(
            RESPONDER_ID,
            """You are Participant B in an economic experiment.
Participant A has been endowed with {{state.total_amount}} coins.
Participant A has proposed to give you {{state.offer}} coins and keep {{int(state.total_amount) - int(state.offer)}} coins for themselves.

You can ACCEPT or REJECT this proposal.
- If you ACCEPT, you get {{state.offer}} and A gets {{int(state.total_amount) - int(state.offer)}}.
- If you REJECT, both of you get 0.

Do you accept or reject?
Reply with ONLY a JSON object: {"decision": "ACCEPT" or "REJECT"}""",
            "responder_output"
        ),
        # Step 4: Calculate Payoffs (Code)
        create_code_step(
            """
data = extract_json(state['responder_output'])
decision = data.get('decision', 'REJECT').upper()
state['decision'] = decision

if decision == 'ACCEPT':
    payoff_a = int(state['total_amount']) - int(state['offer'])
    payoff_b = int(state['offer'])
else:
    payoff_a = 0
    payoff_b = 0

state['payoff_a'] = payoff_a
state['payoff_b'] = payoff_b
print(f"Result: {decision}. Payoffs: A={payoff_a}, B={payoff_b}")
"""
        )
    ]
}

# --- Simulation 2: Ultimatum Game (Framing - Moral/Community) ---
sim_framing_id = str(uuid.uuid4())
sim_framing = {
    "id": sim_framing_id,
    "name": "Ultimatum Game - Framing (Community)",
    "description": "Ultimatum Game with community/fairness framing. Proposer shares resources with a community member.",
    "variables": [
        {"key": "total_amount", "value": "100"},
        {"key": "offer", "value": "0"},
        {"key": "decision", "value": ""}
    ],
    "steps": [
        # Step 1: Proposer makes an offer (Framed)
        create_agent_step(
            PROPOSER_ID,
            """You are a member of a close-knit community.
You have received a community grant of {{state.total_amount}} coins to share with your neighbor (Participant B).
Fairness and mutual support are core values of your community.
You need to propose how much of this grant to share with your neighbor.
If your neighbor feels the offer is unfair and rejects it, the grant is returned to the fund and neither of you gets anything.

How many coins do you offer to your neighbor?
Reply with ONLY a JSON object: {"offer": integer}""",
            "proposer_output"
        ),
        # Step 2: Extract offer
        create_code_step(
            """
data = extract_json(state['proposer_output'])
if data and 'offer' in data:
    state['offer'] = int(data['offer'])
else:
    state['offer'] = 0
print(f"Neighbor A offered: {state['offer']}")
"""
        ),
        # Step 3: Responder decides (Framed)
        create_agent_step(
            RESPONDER_ID,
            """You are a member of a close-knit community.
Your neighbor (Participant A) received a community grant of {{state.total_amount}} coins.
They have offered to share {{state.offer}} coins with you, keeping {{int(state.total_amount) - int(state.offer)}} for themselves.
As a community member, you value fairness but also harmony.

Do you accept this sharing arrangement?
- If you ACCEPT, the funds are distributed as proposed.
- If you REJECT, the grant is lost to both of you.

Reply with ONLY a JSON object: {"decision": "ACCEPT" or "REJECT"}""",
            "responder_output"
        ),
        # Step 4: Calculate Payoffs
        create_code_step(
            """
data = extract_json(state['responder_output'])
decision = data.get('decision', 'REJECT').upper()
state['decision'] = decision

if decision == 'ACCEPT':
    payoff_a = int(state['total_amount']) - int(state['offer'])
    payoff_b = int(state['offer'])
else:
    payoff_a = 0
    payoff_b = 0

state['payoff_a'] = payoff_a
state['payoff_b'] = payoff_b
print(f"Community Result: {decision}. Payoffs: A={payoff_a}, B={payoff_b}")
"""
        )
    ]
}

# Add to DB
simulations_db[sim_baseline_id] = sim_baseline
simulations_db[sim_framing_id] = sim_framing

# Save back
with open(SIMULATIONS_FILE, "w") as f:
    json.dump(simulations_db, f, indent=2, ensure_ascii=False)

print(f"Successfully created 2 simulations:")
print(f"1. {sim_baseline['name']} (ID: {sim_baseline_id})")
print(f"2. {sim_framing['name']} (ID: {sim_framing_id})")
