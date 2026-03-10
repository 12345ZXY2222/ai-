from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class AgentCreateRequest(BaseModel):
    name: str
    provider: str  # 'deepseek', 'zhipu', 'custom'
    model: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    usage_example: Optional[str] = None # For custom generation
    persona: Optional[str] = None # Initial system prompt / personality
    long_term_memory: List[str] = [] # List of facts/memories

class AgentUpdateRequest(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    usage_example: Optional[str] = None
    persona: Optional[str] = None
    long_term_memory: Optional[List[str]] = None

class AgentResponse(BaseModel):
    id: str
    name: str
    provider: str
    model: str
    base_url: Optional[str]
    persona: Optional[str] = None
    long_term_memory: List[str] = []
    relationships: List[str] = [] # Computed relationship descriptions
    files: List[str] = [] # List of uploaded filenames
    # api_key should be hidden in real app
    custom_code: Optional[str] = None
    usage_example: Optional[str] = None # The actual adapter code

class RelationshipCreateRequest(BaseModel):
    source_agent_id: str
    target_agent_id: str
    relationship_type: str # e.g. "parent", "teacher", "colleague"

class RelationshipResponse(BaseModel):
    id: str
    source_agent_id: str
    target_agent_id: str
    relationship_type: str

class GenerateCodeRequest(BaseModel):
    model_config = {'protected_namespaces': ()}
    model_name: str
    base_url: Optional[str]
    api_key: Optional[str] = None
    usage_example: str
    input_modality: str = "text" # "text", "text_image", "audio"
    output_modality: str = "text" # "text", "image", "video", "audio"

class GenerateCodeResponse(BaseModel):
    generated_code: str
    explanation: Optional[str] = None

class FixCodeRequest(BaseModel):
    code: str
    error: str

class FixCodeResponse(BaseModel):
    fixed_code: str
    explanation: Optional[str] = None

class ChatRequest(BaseModel):
    agent_id: str
    messages: List[Dict[str, str]]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1536
