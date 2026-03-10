
try:
    from app.models.simulation import SimulationStep
    print("SimulationStep imported successfully")
except Exception as e:
    print(f"Error importing SimulationStep: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.models.agent import GenerateCodeRequest
    print("GenerateCodeRequest imported successfully")
except Exception as e:
    print(f"Error importing GenerateCodeRequest: {e}")
    import traceback
    traceback.print_exc()
