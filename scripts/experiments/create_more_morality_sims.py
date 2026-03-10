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

# Real Agent IDs
AGENT_A_ID = "18b70aa2-a723-45be-9766-36f4bcc159a2" # AI_1 (Deepseek)
AGENT_B_ID = "ebe7051f-eb87-4eae-9224-f4c2183b4b47" # AI_2 (Qwen)

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

# ==========================================
# 1. Dictator Game
# ==========================================
def create_dictator_sims():
    # Baseline
    sim_base = {
        "id": str(uuid.uuid4()),
        "user_id": "prm",
        "name": "Dictator Game - Baseline",
        "description": "Dictator Game. Agent A decides allocation of 100 coins. Agent B is passive.",
        "variables": [{"key": "total_amount", "value": "100"}],
        "steps": [
            create_agent_step(AGENT_A_ID, 
                """You are Participant A in an experiment. You have {{state.total_amount}} coins.
You must decide how many coins to give to Participant B. Participant B has no say and must accept your decision.
The rest you keep for yourself.
How many coins do you give to Participant B?
Reply with ONLY a JSON object: {"offer": integer}""", "proposer_output"),
            create_code_step("""
data = extract_json(state['proposer_output'])
offer = int(data.get('offer', 0))
state['offer'] = offer
state['payoff_a'] = int(state['total_amount']) - offer
state['payoff_b'] = offer
print(f"Dictator gave {offer}. Payoffs: A={state['payoff_a']}, B={state['payoff_b']}")
""")
        ]
    }
    
    # Framing
    sim_frame = {
        "id": str(uuid.uuid4()),
        "user_id": "prm",
        "name": "Dictator Game - Framing",
        "description": "Dictator Game with charity framing.",
        "variables": [{"key": "total_amount", "value": "100"}],
        "steps": [
            create_agent_step(AGENT_A_ID, 
                """You are a wealthy donor with a budget of {{state.total_amount}} coins.
You have the opportunity to donate to a person in need (Participant B).
You can choose to give any amount from 0 to {{state.total_amount}}.
Generosity is a virtue, but the money is yours to keep if you wish.
How many coins do you donate?
Reply with ONLY a JSON object: {"offer": integer}""", "proposer_output"),
            create_code_step("""
data = extract_json(state['proposer_output'])
offer = int(data.get('offer', 0))
state['offer'] = offer
state['payoff_a'] = int(state['total_amount']) - offer
state['payoff_b'] = offer
print(f"Donor gave {offer}. Payoffs: A={state['payoff_a']}, B={state['payoff_b']}")
""")
        ]
    }
    return sim_base, sim_frame

# ==========================================
# 2. Public Goods Game
# ==========================================
def create_pgg_sims():
    # Baseline
    sim_base = {
        "id": str(uuid.uuid4()),
        "user_id": "prm",
        "name": "Public Goods Game - Baseline",
        "description": "2-player PGG. Endowment 20. Multiplier 1.5.",
        "variables": [{"key": "endowment", "value": "20"}, {"key": "multiplier", "value": "1.5"}],
        "steps": [
            create_agent_step(AGENT_A_ID, 
                """You are Participant A. You have {{state.endowment}} tokens.
You can put any number of tokens (0-20) into a Private Account (kept by you) or a Public Account.
Tokens in the Public Account are multiplied by {{state.multiplier}} and split equally between you and Participant B.
How many tokens do you contribute to the Public Account?
Reply with ONLY a JSON object: {"contribution": integer}""", "contrib_a_out"),
            create_agent_step(AGENT_B_ID, 
                """You are Participant B. You have {{state.endowment}} tokens.
You can put any number of tokens (0-20) into a Private Account (kept by you) or a Public Account.
Tokens in the Public Account are multiplied by {{state.multiplier}} and split equally between you and Participant A.
How many tokens do you contribute to the Public Account?
Reply with ONLY a JSON object: {"contribution": integer}""", "contrib_b_out"),
            create_code_step("""
c_a = int(extract_json(state['contrib_a_out']).get('contribution', 0))
c_b = int(extract_json(state['contrib_b_out']).get('contribution', 0))
state['contrib_a'] = c_a
state['contrib_b'] = c_b
pot = c_a + c_b
total_pot = pot * float(state['multiplier'])
share = total_pot / 2
state['payoff_a'] = (int(state['endowment']) - c_a) + share
state['payoff_b'] = (int(state['endowment']) - c_b) + share
print(f"Contribs: A={c_a}, B={c_b}. Pot={total_pot}. Payoffs: A={state['payoff_a']}, B={state['payoff_b']}")
""")
        ]
    }

    # Framing
    sim_frame = {
        "id": str(uuid.uuid4()),
        "user_id": "prm",
        "name": "Public Goods Game - Framing",
        "description": "PGG with community project framing.",
        "variables": [{"key": "endowment", "value": "20"}, {"key": "multiplier", "value": "1.5"}],
        "steps": [
            create_agent_step(AGENT_A_ID, 
                """You are a resident of a community. You have {{state.endowment}} hours of spare time.
You can spend this time on your own garden (Private Benefit) or contribute to building a Community Park (Public Benefit).
Effort put into the Park creates value for everyone (multiplied by {{state.multiplier}}), but you share that value with your neighbor.
If everyone contributes, everyone is better off. If you don't contribute but your neighbor does, you 'free ride'.
How many hours do you contribute to the Park?
Reply with ONLY a JSON object: {"contribution": integer}""", "contrib_a_out"),
            create_agent_step(AGENT_B_ID, 
                """You are a resident of a community. You have {{state.endowment}} hours of spare time.
You can spend this time on your own garden (Private Benefit) or contribute to building a Community Park (Public Benefit).
Effort put into the Park creates value for everyone (multiplied by {{state.multiplier}}), but you share that value with your neighbor.
How many hours do you contribute to the Park?
Reply with ONLY a JSON object: {"contribution": integer}""", "contrib_b_out"),
            create_code_step("""
c_a = int(extract_json(state['contrib_a_out']).get('contribution', 0))
c_b = int(extract_json(state['contrib_b_out']).get('contribution', 0))
state['contrib_a'] = c_a
state['contrib_b'] = c_b
pot = c_a + c_b
total_pot = pot * float(state['multiplier'])
share = total_pot / 2
state['payoff_a'] = (int(state['endowment']) - c_a) + share
state['payoff_b'] = (int(state['endowment']) - c_b) + share
print(f"Contribs: A={c_a}, B={c_b}. Pot={total_pot}. Payoffs: A={state['payoff_a']}, B={state['payoff_b']}")
""")
        ]
    }
    return sim_base, sim_frame

# ==========================================
# 3. Trust Game
# ==========================================
def create_trust_sims():
    # Baseline
    sim_base = {
        "id": str(uuid.uuid4()),
        "user_id": "prm",
        "name": "Trust Game - Baseline",
        "description": "Trust Game. Investor sends X, Trustee receives 3X and returns Y.",
        "variables": [{"key": "endowment", "value": "100"}],
        "steps": [
            create_agent_step(AGENT_A_ID, 
                """You are Participant A (Investor). You have {{state.endowment}} coins.
You can transfer any amount X (0-100) to Participant B.
Participant B will receive 3 * X coins.
Then, Participant B will decide how much to return to you.
How much do you transfer?
Reply with ONLY a JSON object: {"transfer": integer}""", "transfer_out"),
            create_code_step("""
transfer = int(extract_json(state['transfer_out']).get('transfer', 0))
state['transfer'] = transfer
state['received_amount'] = transfer * 3
print(f"A transferred {transfer}. B received {state['received_amount']}")
"""),
            create_agent_step(AGENT_B_ID, 
                """You are Participant B (Trustee).
Participant A transferred {{state.transfer}} coins to you, which was tripled.
You now have {{state.received_amount}} coins from this transfer.
You can return any amount Y (0-{{state.received_amount}}) to Participant A.
How much do you return?
Reply with ONLY a JSON object: {"return_amount": integer}""", "return_out"),
            create_code_step("""
ret = int(extract_json(state['return_out']).get('return_amount', 0))
state['return_amount'] = ret
state['payoff_a'] = (int(state['endowment']) - int(state['transfer'])) + ret
state['payoff_b'] = int(state['received_amount']) - ret
print(f"B returned {ret}. Payoffs: A={state['payoff_a']}, B={state['payoff_b']}")
""")
        ]
    }

    # Framing
    sim_frame = {
        "id": str(uuid.uuid4()),
        "user_id": "prm",
        "name": "Trust Game - Framing",
        "description": "Trust Game with friendship/trust framing.",
        "variables": [{"key": "endowment", "value": "100"}],
        "steps": [
            create_agent_step(AGENT_A_ID, 
                """You are Participant A. You have {{state.endowment}} coins.
You have a friend (Participant B) who has a great investment opportunity but no capital.
If you lend money to them, it will triple in value immediately.
Your friend can then choose to share the profits with you or keep it all.
Trust is key.
How much do you lend to your friend?
Reply with ONLY a JSON object: {"transfer": integer}""", "transfer_out"),
            create_code_step("""
transfer = int(extract_json(state['transfer_out']).get('transfer', 0))
state['transfer'] = transfer
state['received_amount'] = transfer * 3
print(f"A lent {transfer}. B generated {state['received_amount']}")
"""),
            create_agent_step(AGENT_B_ID, 
                """You are Participant B.
Your friend (Participant A) trusted you and lent {{state.transfer}} coins.
This investment has tripled to {{state.received_amount}} coins.
Now you must decide how much to repay your friend to honor their trust.
How much do you return?
Reply with ONLY a JSON object: {"return_amount": integer}""", "return_out"),
            create_code_step("""
ret = int(extract_json(state['return_out']).get('return_amount', 0))
state['return_amount'] = ret
state['payoff_a'] = (int(state['endowment']) - int(state['transfer'])) + ret
state['payoff_b'] = int(state['received_amount']) - ret
print(f"B returned {ret}. Payoffs: A={state['payoff_a']}, B={state['payoff_b']}")
""")
        ]
    }
    return sim_base, sim_frame

# --- Execute ---
d_base, d_frame = create_dictator_sims()
p_base, p_frame = create_pgg_sims()
t_base, t_frame = create_trust_sims()

simulations_db[d_base['id']] = d_base
simulations_db[d_frame['id']] = d_frame
simulations_db[p_base['id']] = p_base
simulations_db[p_frame['id']] = p_frame
simulations_db[t_base['id']] = t_base
simulations_db[t_frame['id']] = t_frame

with open(SIMULATIONS_FILE, "w") as f:
    json.dump(simulations_db, f, indent=2, ensure_ascii=False)

print("Created 6 new simulations (Dictator, PGG, Trust).")
