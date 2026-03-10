import json
import os
import sys
import uuid
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from jinja2 import Template
import re
import time
import copy

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))
os.environ['AI_PROVIDER'] = 'deepseek'

try:
    from app.core.adapter import ai_chat
except ImportError as e:
    print(f"Error importing ai_chat: {e}")
    sys.exit(1)

# --- Configuration ---
AGENTS_FILE = "/home/peirm/ai模拟平台/backend/data/agents.json"
RESULTS_DIR = "/home/peirm/ai模拟平台/论文/experiment_results"
CSV_FILE = os.path.join(RESULTS_DIR, "complex_games_results.csv")

MODELS = {
    "DeepSeek": "18b70aa2-a723-45be-9766-36f4bcc159a2",
    "Qwen": "ebe7051f-eb87-4eae-9224-f4c2183b4b47"
}

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
        return json.loads(text)
    except:
        return {} # Return empty dict on failure to avoid .get() error

# --- Simulation Definitions ---

def create_rpd_sim(rounds=10):
    steps = []
    for r in range(1, rounds + 1):
        # Player A
        steps.append({
            "type": "agent",
            "role": "A",
            "prompt_template": """You are Player A in a Repeated Prisoner's Dilemma (Round {{r}} of {{rounds}}).
Payoff Matrix:
- Both Cooperate: Both get 3
- You Cooperate, Opponent Defects: You 0, Opponent 5
- You Defect, Opponent Cooperates: You 5, Opponent 0
- Both Defect: Both get 1

History: {{state.history_str}}

Your goal is to maximize your TOTAL payoff over 10 rounds.
Do you COOPERATE or DEFECT?
Reply JSON: {"action": "COOPERATE" or "DEFECT"}""",
            "output_var": f"action_a_{r}",
            "round": r
        })
        # Player B
        steps.append({
            "type": "agent",
            "role": "B",
            "prompt_template": """You are Player B in a Repeated Prisoner's Dilemma (Round {{r}} of {{rounds}}).
Payoff Matrix:
- Both Cooperate: Both get 3
- You Cooperate, Opponent Defects: You 0, Opponent 5
- You Defect, Opponent Cooperates: You 5, Opponent 0
- Both Defect: Both get 1

History: {{state.history_str}}

Your goal is to maximize your TOTAL payoff over 10 rounds.
Do you COOPERATE or DEFECT?
Reply JSON: {"action": "COOPERATE" or "DEFECT"}""",
            "output_var": f"action_b_{r}",
            "round": r
        })
        # Calculation
        steps.append({
            "type": "code",
            "code_snippet": f"""
raw_a = state.get('action_a_{r}', '{{}}')
raw_b = state.get('action_b_{r}', '{{}}')
data_a = extract_json(raw_a)
data_b = extract_json(raw_b)

# Fallback if extraction failed or returned non-dict
if not isinstance(data_a, dict): data_a = {{}}
if not isinstance(data_b, dict): data_b = {{}}

a_act = data_a.get('action', 'DEFECT').upper()
b_act = data_b.get('action', 'DEFECT').upper()
state['moves'].append((a_act, b_act))

# Payoffs
if a_act == 'COOPERATE' and b_act == 'COOPERATE':
    pa, pb = 3, 3
elif a_act == 'COOPERATE' and b_act == 'DEFECT':
    pa, pb = 0, 5
elif a_act == 'DEFECT' and b_act == 'COOPERATE':
    pa, pb = 5, 0
else:
    pa, pb = 1, 1

state['payoff_a'] += pa
state['payoff_b'] += pb
state['history_str'] += f"Round {r}: A={{a_act}}, B={{b_act}}\\n"
print(f"Round {r}: A={{a_act}}, B={{b_act}} -> Payoffs: {{pa}}, {{pb}}")
"""
        })
    return {
        "name": "Repeated Prisoner's Dilemma",
        "variables": [
            {"key": "history_str", "value": ""},
            {"key": "payoff_a", "value": 0},
            {"key": "payoff_b", "value": 0},
            {"key": "moves", "value": []}
        ],
        "steps": steps
    }

def create_centipede_sim():
    # 6 Nodes
    # Node 1 (A): Take(4,1), Pass->
    # Node 2 (B): Take(2,8), Pass->
    # Node 3 (A): Take(16,4), Pass->
    # Node 4 (B): Take(8,32), Pass->
    # Node 5 (A): Take(64,16), Pass->
    # Node 6 (B): Take(32,128), Pass-> End(64,64)
    
    payoffs = [
        (4, 1), (2, 8), (16, 4), (8, 32), (64, 16), (32, 128)
    ]
    
    steps = []
    for i in range(6):
        node = i + 1
        player = "A" if node % 2 != 0 else "B"
        
        steps.append({
            "type": "agent",
            "role": player,
            "prompt_template": f"""You are Player {player} in a Centipede Game.
Node {node} of 6.
If you TAKE: Game ends. Payoffs: A={payoffs[i][0]}, B={payoffs[i][1]}.
If you PASS: Game moves to Node {node+1}. Pot grows.

Full Structure:
1 (A): Take(4,1) -> Pass
2 (B): Take(2,8) -> Pass
3 (A): Take(16,4) -> Pass
4 (B): Take(8,32) -> Pass
5 (A): Take(64,16) -> Pass
6 (B): Take(32,128) -> Pass -> End(64,64)

Do you TAKE or PASS?
Reply JSON: {{"action": "TAKE" or "PASS"}}""",
            "output_var": f"action_{node}",
            "node": node
        })
        
        steps.append({
            "type": "code",
            "code_snippet": f"""
raw = state.get('action_{node}', '{{}}')
data = extract_json(raw)
if not isinstance(data, dict): data = {{}}
act = data.get('action', 'TAKE').upper()
state['last_node'] = {node}
state['last_action'] = act

if act == 'TAKE':
    state['payoff_a'] = {payoffs[i][0]}
    state['payoff_b'] = {payoffs[i][1]}
    state['game_over'] = True
    print(f"Node {node} ({player}): TAKE. Game Over.")
else:
    print(f"Node {node} ({player}): PASS.")
    if {node} == 6:
        state['payoff_a'] = 64
        state['payoff_b'] = 64
        state['game_over'] = True
        print("End of Game. Both get 64.")
"""
        })
        
    return {
        "name": "Centipede Game",
        "variables": [
            {"key": "payoff_a", "value": 0},
            {"key": "payoff_b", "value": 0},
            {"key": "game_over", "value": False},
            {"key": "last_node", "value": 0}
        ],
        "steps": steps
    }

# --- Execution Engine ---

def run_simulation(sim_data, agents_db, model_id, model_name):
    state = {v['key']: v['value'] for v in sim_data.get('variables', [])}
    if 'moves' in state: state['moves'] = [] # Ensure list is fresh
    
    print(f"--- Running {sim_data['name']} ({model_name}) ---")
    
    for step in sim_data['steps']:
        if state.get('game_over', False):
            break
            
        if step['type'] == 'agent':
            agent = agents_db.get(model_id)
            
            # Render Prompt
            template = Template(step['prompt_template'])
            prompt = template.render(state=state, r=step.get('round'), rounds=10)
            
            try:
                response = ai_chat(
                    messages_or_prompt=[{"role": "user", "content": prompt}],
                    prompt_content=prompt,
                    model=agent.get("model"),
                    api_key=agent.get("api_key"),
                    base_url=agent.get("base_url"),
                    temperature=0.5
                )
                content = response.get('content', '')
                if step.get('output_var'):
                    state[step['output_var']] = content
            except Exception as e:
                print(f"Error: {e}")
                
        elif step['type'] == 'code':
            local_scope = {"state": state, "extract_json": extract_json}
            exec(step['code_snippet'], {}, local_scope)
            
    return state

# --- Main ---

def main():
    agents_db = load_json(AGENTS_FILE)
    results = []
    
    # 1. Repeated Prisoner's Dilemma
    sim_rpd = create_rpd_sim(10)
    for model_name, model_id in MODELS.items():
        for i in range(3): # 3 Runs
            final_state = run_simulation(sim_rpd, agents_db, model_id, model_name)
            
            # Record each round
            for r_idx, (ma, mb) in enumerate(final_state['moves']):
                results.append({
                    "Game": "RPD",
                    "Model": model_name,
                    "Run": i+1,
                    "Round": r_idx + 1,
                    "Action_A": 1 if ma == 'COOPERATE' else 0,
                    "Action_B": 1 if mb == 'COOPERATE' else 0,
                    "Outcome": f"{ma}-{mb}"
                })
    
    # 2. Centipede Game
    sim_cent = create_centipede_sim()
    cent_results = []
    for model_name, model_id in MODELS.items():
        for i in range(5): # 5 Runs
            final_state = run_simulation(sim_cent, agents_db, model_id, model_name)
            cent_results.append({
                "Game": "Centipede",
                "Model": model_name,
                "Run": i+1,
                "Stop_Node": final_state['last_node'] if final_state['last_action'] == 'TAKE' else 7, # 7 means finished
                "Payoff_A": final_state['payoff_a'],
                "Payoff_B": final_state['payoff_b']
            })

    # Save RPD Data
    df_rpd = pd.DataFrame(results)
    df_rpd.to_csv(os.path.join(RESULTS_DIR, "rpd_results.csv"), index=False)
    
    # Save Centipede Data
    df_cent = pd.DataFrame(cent_results)
    df_cent.to_csv(os.path.join(RESULTS_DIR, "centipede_results.csv"), index=False)
    
    # --- Plotting ---
    sns.set_theme(style="whitegrid")
    
    # Plot 1: RPD Cooperation Rate over Rounds
    df_rpd['Cooperation_Rate'] = (df_rpd['Action_A'] + df_rpd['Action_B']) / 2
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df_rpd, x="Round", y="Cooperation_Rate", hue="Model", marker="o")
    plt.title("Evolution of Cooperation in Repeated Prisoner's Dilemma (10 Rounds)")
    plt.ylim(-0.1, 1.1)
    plt.savefig(os.path.join(RESULTS_DIR, "rpd_cooperation.png"))
    
    # Plot 2: Centipede Stop Node
    plt.figure(figsize=(8, 6))
    sns.histplot(data=df_cent, x="Stop_Node", hue="Model", multiple="dodge", bins=range(1, 9), discrete=True, shrink=0.8)
    plt.title("Stopping Node in Centipede Game (Max 6)")
    plt.xticks(range(1, 8), ['1', '2', '3', '4', '5', '6', 'End'])
    plt.savefig(os.path.join(RESULTS_DIR, "centipede_stop_node.png"))
    
    print("Experiments completed and plots generated.")

if __name__ == "__main__":
    main()
