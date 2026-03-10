import json
import os
import sys
import uuid
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from jinja2 import Template
import re
import io
from contextlib import redirect_stdout
import time

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

# Force AI_PROVIDER to deepseek to use the OpenAI-compatible adapter logic
os.environ['AI_PROVIDER'] = 'deepseek'

# Try importing ai_chat. If it fails (due to missing deps), we might need to mock or fix.
try:
    from app.core.adapter import ai_chat
except ImportError as e:
    print(f"Error importing ai_chat: {e}")
    sys.exit(1)

# --- Configuration ---
SIMULATIONS_FILE = "/home/peirm/ai模拟平台/backend/data/simulations.json"
AGENTS_FILE = "/home/peirm/ai模拟平台/backend/data/agents.json"
RESULTS_DIR = "/home/peirm/ai模拟平台/论文/experiment_results"
CSV_FILE = os.path.join(RESULTS_DIR, "morality_results.csv")

# Real Agent IDs (from prm user)
PROPOSER_AGENT_ID = "18b70aa2-a723-45be-9766-36f4bcc159a2" # AI_1 (Deepseek)
RESPONDER_AGENT_ID = "ebe7051f-eb87-4eae-9224-f4c2183b4b47" # AI_2 (Qwen)

# --- Helper Functions ---

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def extract_json(text):
    if not isinstance(text, str):
        return text
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass
    match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass
    try:
        return json.loads(text)
    except:
        return text

def run_simulation(sim_data, agents_db, run_id):
    # Initialize State
    state = {v['key']: v['value'] for v in sim_data.get('variables', [])}
    history = []
    
    print(f"--- Running Simulation: {sim_data['name']} (Run {run_id}) ---")
    
    for step in sim_data['steps']:
        # print(f"Executing Step: {step['type']}")
        
        if step['type'] == 'agent':
            agent_id = step['agent_ids'][0]
            agent = agents_db.get(agent_id)
            if not agent:
                print(f"Agent {agent_id} not found!")
                continue
            
            # Render Prompt
            template = Template(step['prompt_template'])
            prompt = template.render(state=state, int=int, str=str, len=len)
            
            # Call AI
            print(f"  Prompt: {prompt[:50]}...")
            try:
                response = ai_chat(
                    messages_or_prompt=[{"role": "user", "content": prompt}],
                    prompt_content=prompt,
                    model=agent.get("model"),
                    api_key=agent.get("api_key"),
                    base_url=agent.get("base_url"),
                    temperature=0.7 # Some randomness
                )
                content = response.get('content', '')
                print(f"  Response: {content}...")
                
                # Update State
                if step.get('output_var'):
                    state[step['output_var']] = content
                    
                history.append({"step": step['id'], "role": "agent", "content": content})
                
            except Exception as e:
                print(f"  Error calling AI: {e}")
        
        elif step['type'] == 'code':
            code = step['code_snippet']
            # Execute Code
            local_scope = {
                "state": state,
                "extract_json": extract_json,
                "json": json
            }
            try:
                exec(code, {}, local_scope)
            except Exception as e:
                print(f"  Error executing code: {e}")

    return state

# --- Main Execution ---

def main():
    # 1. Load Data
    sims_db = load_json(SIMULATIONS_FILE)
    agents_db = load_json(AGENTS_FILE)
    
    # 2. Identify Target Simulations
    target_sims = []
    for sim_id, sim in sims_db.items():
        name = sim.get("name", "")
        if any(x in name for x in ["Ultimatum Game", "Dictator Game", "Public Goods Game", "Trust Game"]):
            target_sims.append(sim)
            
    print(f"Found {len(target_sims)} simulations to run.")

    # 3. Run Experiments
    results = []
    NUM_RUNS = 3 # Reduced to 3 to save time/tokens, increase for real exp
    
    for sim in target_sims:
        sim_name = sim["name"]
        game_type = sim_name.split(" - ")[0]
        condition = "Baseline" if "Baseline" in sim_name else "Framing"
        
        for i in range(NUM_RUNS):
            final_state = run_simulation(sim, agents_db, i+1)
            
            # Collect Data based on Game Type
            row = {
                "Game": game_type,
                "Condition": condition,
                "Run": i + 1,
                "Payoff_A": int(final_state.get("payoff_a", 0)),
                "Payoff_B": int(final_state.get("payoff_b", 0))
            }
            
            if "Ultimatum" in game_type:
                row["Action_A"] = int(final_state.get("offer", 0)) # Offer
                row["Action_B"] = 1 if final_state.get("decision") == "ACCEPT" else 0 # Accept/Reject
            elif "Dictator" in game_type:
                row["Action_A"] = int(final_state.get("offer", 0)) # Offer
                row["Action_B"] = 0 # Passive
            elif "Public Goods" in game_type:
                row["Action_A"] = int(final_state.get("contrib_a", 0)) # Contribution
                row["Action_B"] = int(final_state.get("contrib_b", 0)) # Contribution
            elif "Trust" in game_type:
                row["Action_A"] = int(final_state.get("transfer", 0)) # Transfer
                row["Action_B"] = int(final_state.get("return_amount", 0)) # Return
                
            results.append(row)
            time.sleep(1)

    # 4. Save Results
    df = pd.DataFrame(results)
    df.to_csv(CSV_FILE, index=False)
    print(f"Results saved to {CSV_FILE}")
    
    # 5. Analysis & Visualization
    print("\n--- Analysis ---")
    print(df.groupby(["Game", "Condition"])[["Action_A", "Action_B", "Payoff_A", "Payoff_B"]].mean())
    
    # Plot: Action A Distribution by Game and Condition
    plt.figure(figsize=(12, 8))
    sns.barplot(x="Game", y="Action_A", hue="Condition", data=df)
    plt.title("Primary Action (Offer/Contrib/Transfer) by Game & Condition")
    plt.ylabel("Amount")
    plt.savefig(os.path.join(RESULTS_DIR, "all_games_action_a.png"))
    print("Generated all_games_action_a.png")
    
    # Plot: Payoff Comparison
    df_melted = df.melt(id_vars=["Game", "Condition"], value_vars=["Payoff_A", "Payoff_B"], var_name="Player", value_name="Payoff")
    plt.figure(figsize=(12, 8))
    sns.barplot(x="Game", y="Payoff", hue="Player", data=df_melted)
    plt.title("Average Payoffs by Game & Player")
    plt.savefig(os.path.join(RESULTS_DIR, "all_games_payoffs.png"))
    print("Generated all_games_payoffs.png")
    plt.title("Acceptance Rate: Baseline vs Framing")
    plt.ylim(0, 1.1)
    plt.savefig(os.path.join(RESULTS_DIR, "acceptance_rate.png"))
    print("Generated acceptance_rate.png")

if __name__ == "__main__":
    main()
