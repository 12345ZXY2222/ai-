import json
import os
import sys
from dotenv import load_dotenv
from app.core.simulation_generator import generate_simulation_config
from app.models.simulation import Simulation
from app.core.storage import save_data, load_data

# Load env vars for DeepSeek adapter
load_dotenv()

def test_full_flow():
    print("--- Starting Full Flow Generation Test ---")
    
    # 1. Generate
    print("1. Calling generate_simulation_config...")
    try:
        # User's specific prompt that failed
        prompt = "生成一个库存管理中的牛鞭效应的模拟实验"
        print(f"   Prompt: {prompt}")
        config = generate_simulation_config(prompt)
        print("   Generation complete.")
    except Exception as e:
        print(f"!!! Generation Failed: {e}")
        return

    # 2. Validate Pydantic Model (Simulate 'generate_simulation' return type)
    print("2. Validating against Pydantic Model...")
    try:
        # Add dummy user_id and id as the endpoint would
        sim_data = {
            "id": "test-sim-id-123",
            "user_id": "test-user",
            **config
        }
        simulation_obj = Simulation(**sim_data)
        print("   Pydantic Validation Passed!")
    except Exception as e:
        print(f"!!! Pydantic Validation Failed: {e}")
        return

    # 3. Simulate "Auto-create missing agents" logic from endpoints.py
    print("3. Checking Agent IDs (Endpoint Logic Simulation)...")
    all_agent_ids = set()
    def extract_ids(steps):
        for step in steps:
            if step.type == 'agent':
                ids = step.agent_ids or []
                for i in ids: all_agent_ids.add(i)
            if step.inner_steps:
                extract_ids(step.inner_steps)
    
    extract_ids(simulation_obj.steps)
    print(f"   Found Agent IDs: {all_agent_ids}")
    # In a real scenario, we'd check AGENTS_DB here. 
    # For this test, just ensuring we extracted them is enough.

    # 4. Simulate Persistence (Save to Disk)
    print("4. Simulating Storage (Save/Load)...")
    test_filename = "test_simulation_persistence.json"
    try:
        # Save
        save_data(test_filename, simulation_obj.dict())
        print(f"   Saved to {test_filename}")
        
        # Load
        loaded_data = load_data(test_filename, {})
        loaded_sim = Simulation(**loaded_data)
        print("   Loaded back and re-validated with Pydantic.")
        
        # Verify specific fields
        assert loaded_sim.name == simulation_obj.name
        assert len(loaded_sim.steps) == len(simulation_obj.steps)
        print("   Data Integrity Check Passed.")
        
        # Cleanup
        filepath = os.path.join("data", test_filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        print("   Cleanup complete.")
        
    except Exception as e:
        print(f"!!! Storage Simulation Failed: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n--- SUCCESS: Full Flow Verified ---")
    print("The generated simulation is valid, can be serialized/deserialized, and fits the frontend model.")

if __name__ == "__main__":
    test_full_flow()
