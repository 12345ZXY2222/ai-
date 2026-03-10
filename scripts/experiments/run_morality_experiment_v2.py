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
import copy

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
CSV_FILE = os.path.join(RESULTS_DIR, "morality_results_v2.csv")

# Models to Test (Homogeneous Pairs)
MODELS = {
    "DeepSeek": "18b70aa2-a723-45be-9766-36f4bcc159a2",
    "Qwen": "ebe7051f-eb87-4eae-9224-f4c2183b4b47"
}

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
    # Try to find JSON block
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
    # Try raw
    try:
        return json.loads(text)
    except:
        return text

def run_simulation(sim_data, agents_db, run_id, model_name):
    # Initialize State
    state = {v['key']: v['value'] for v in sim_data.get('variables', [])}
    history = []
    
    print(f"--- Running {model_name}: {sim_data['name']} (Run {run_id}) ---")
    
    for step in sim_data['steps']:
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
            # print(f"  Prompt: {prompt[:50]}...")
            try:
                response = ai_chat(
                    messages_or_prompt=[{"role": "user", "content": prompt}],
                    prompt_content=prompt,
                    model=agent.get("model"),
                    api_key=agent.get("api_key"),
                    base_url=agent.get("base_url"),
                    temperature=0.7 
                )
                content = response.get('content', '')
                # print(f"  Response: {content[:50]}...")
                
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
    NUM_RUNS = 3 
    
    for model_name, model_id in MODELS.items():
        print(f"\n=== Testing Model: {model_name} ===")
        
        for sim in target_sims:
            # Create a copy of the simulation to modify agents
            sim_copy = copy.deepcopy(sim)
            
            # Replace ALL agents in the simulation with the current model
            for step in sim_copy['steps']:
                if step['type'] == 'agent':
                    step['agent_ids'] = [model_id]
            
            sim_name = sim_copy["name"]
            game_type = sim_name.split(" - ")[0]
            condition = "Baseline" if "Baseline" in sim_name else "Framing"
            
            for i in range(NUM_RUNS):
                final_state = run_simulation(sim_copy, agents_db, i+1, model_name)
                
                # Collect Data
                row = {
                    "Model": model_name,
                    "Game": game_type,
                    "Condition": condition,
                    "Run": i + 1,
                    "Payoff_A": int(final_state.get("payoff_a", 0)),
                    "Payoff_B": int(final_state.get("payoff_b", 0))
                }
                
                if "Ultimatum" in game_type:
                    row["Action_A"] = int(final_state.get("offer", 0)) 
                    row["Action_B"] = 1 if final_state.get("decision") == "ACCEPT" else 0 
                elif "Dictator" in game_type:
                    row["Action_A"] = int(final_state.get("offer", 0)) 
                    row["Action_B"] = 0 
                elif "Public Goods" in game_type:
                    row["Action_A"] = int(final_state.get("contrib_a", 0)) 
                    row["Action_B"] = int(final_state.get("contrib_b", 0)) 
                elif "Trust" in game_type:
                    row["Action_A"] = int(final_state.get("transfer", 0)) 
                    row["Action_B"] = int(final_state.get("return_amount", 0)) 
                    
                results.append(row)
                time.sleep(0.5)

    # 4. Save Results
    df = pd.DataFrame(results)
    df.to_csv(CSV_FILE, index=False)
    print(f"Results saved to {CSV_FILE}")
    
    # 5. Analysis & Visualization
    print("\n--- Analysis ---")
    print(df.groupby(["Model", "Game", "Condition"])[["Action_A", "Action_B"]].mean())
    
    # Plot 1: Action A by Game, Condition, and Model
    plt.figure(figsize=(14, 8))
    sns.catplot(
        data=df, x="Game", y="Action_A", hue="Condition", col="Model", 
        kind="bar", height=5, aspect=1.2,
        errorbar=None
    )
    plt.savefig(os.path.join(RESULTS_DIR, "model_comparison_action_a.png"))
    print("Generated model_comparison_action_a.png")
    
    # Plot 2: Payoff Distribution
    df_melted = df.melt(id_vars=["Model", "Game", "Condition"], value_vars=["Payoff_A", "Payoff_B"], var_name="Player", value_name="Payoff")
    plt.figure(figsize=(14, 8))
    sns.catplot(
        data=df_melted, x="Game", y="Payoff", hue="Player", col="Model", row="Condition",
        kind="bar", height=4, aspect=1.5,
        errorbar=None
    )
    plt.savefig(os.path.join(RESULTS_DIR, "model_comparison_payoffs.png"))
    print("Generated model_comparison_payoffs.png")

if __name__ == "__main__":
    main()
