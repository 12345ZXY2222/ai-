
import sys
import os
import json
import uuid
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Add current directory to sys.path so we can import app modules
sys.path.append(os.getcwd())

from app.core.simulation_generator import generate_simulation_config
from app.models.simulation import Simulation, SimulationStep

def validate_step_recursive(step: Dict[str, Any], path: str = ""):
    print(f"Validating step {path} ({step.get('id')})...")
    
    # Check required fields
    if 'id' not in step:
        print(f"ERROR: Step at {path} missing 'id'")
        step['id'] = str(uuid.uuid4()) # Fix it
        
    if 'type' not in step:
        print(f"ERROR: Step at {path} missing 'type'")
        step['type'] = 'agent' # Fix it

    # Check list fields are lists
    if 'agent_ids' in step and not isinstance(step['agent_ids'], list):
        print(f"ERROR: Step {path} 'agent_ids' is not a list: {step['agent_ids']}")
        step['agent_ids'] = []
        
    if 'inner_steps' in step:
        if step['inner_steps'] is None:
             step['inner_steps'] = []
        elif not isinstance(step['inner_steps'], list):
             print(f"ERROR: Step {path} 'inner_steps' is not a list")
             step['inner_steps'] = []
        
        for i, inner in enumerate(step['inner_steps']):
            validate_step_recursive(inner, f"{path}.inner[{i}]")

def test_generation():
    print("--- Starting Generation Test ---")
    prompt = "Create a debate between two agents about the future of AI. One is optimistic, one is pessimistic. They should take turns speaking 3 times each. Finally, a judge agent decides the winner."
    
    try:
        # 1. Generate Config (Raw Dict)
        print("1. Calling generate_simulation_config...")
        config = generate_simulation_config(prompt)
        print("   Generation complete.")
        print(f"   Name: {config.get('name')}")
        print(f"   Steps count: {len(config.get('steps', []))}")
        
        # 2. Validate Structure Manually (Simulate what might happen in endpoint)
        steps = config.get("steps", [])
        for i, step in enumerate(steps):
            validate_step_recursive(step, f"root[{i}]")
            
        # 3. Pydantic Validation
        print("2. Validating against Pydantic Model...")
        sim_data = {
            "id": str(uuid.uuid4()),
            "name": config.get("name", "Generated Simulation"),
            "description": config.get("description", ""),
            "steps": steps,
            "variables": config.get("variables", []),
            "user_id": "test_user"
        }
        
        sim_model = Simulation(**sim_data)
        print("   Pydantic Validation Passed!")
        
        # 4. Output Result
        print("3. Final JSON Structure:")
        print(json.dumps(sim_model.dict(), indent=2))
        
    except Exception as e:
        print(f"!!! TEST FAILED !!!")
        print(e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_generation()
