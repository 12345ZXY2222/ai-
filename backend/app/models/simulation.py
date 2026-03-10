from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union

class SimulationStep(BaseModel):
    id: str
    type: str = "agent" # 'agent', 'code', 'loop', 'dialogue'
    agent_ids: Optional[List[str]] = [] # List of agents acting in this step
    agent_id: Optional[str] = None # Legacy field for backward compatibility
    prompt_template: Optional[str] = None # For agent steps
    code_snippet: Optional[str] = None # For code steps or loop condition
    loop_condition: Optional[str] = None # For loop steps (Python expression returning bool)
    output_var: Optional[str] = None # Variable to store result
    inner_steps: Optional[List['SimulationStep']] = [] # For loops
    repeat_count: Union[int, str] = 1 # How many times to run this step
    files: Optional[List[str]] = [] # Attached files
    output_format: Optional[str] = "raw" # 'raw', 'text', 'image', 'video'
    execution_mode: Optional[str] = "parallel" # 'serial', 'parallel'
    use_rag: bool = True # Whether to use RAG memory

    # --- Dialogue step config ---
    dialogue_max_turns: Optional[int] = 6
    dialogue_auto_partner: Optional[bool] = True
    dialogue_partner_id: Optional[str] = None
    dialogue_end_marker: Optional[str] = "END_DIALOGUE"

SimulationStep.update_forward_refs()

class Simulation(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    steps: List[SimulationStep]
    variables: List[Dict[str, str]]

class SimulationRun(BaseModel):
    id: Optional[str] = None
    simulation_id: Optional[str] = None
    timestamp: Optional[float] = None
    history: List[Dict[str, Any]]
    final_world_state: Dict[str, Any]

class SimulationRunRequest(BaseModel):
    steps: List[SimulationStep]
    current_step_index: int
    history: List[Dict[str, Any]] = [] 
    world_state: Dict[str, Any] = {} # Global variables

class SimulationStepResponse(BaseModel):
    content: str
    new_history_items: List[Dict[str, Any]]
    updated_world_state: Dict[str, Any]

class SimulationGenerateRequest(BaseModel):
    prompt: str
    file_content: Optional[str] = None
    file_names: List[str] = [] # List of filenames uploaded to temp storage
