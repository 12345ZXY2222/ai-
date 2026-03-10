import json
import re
from typing import List, Dict, Any, Optional
from app.core.adapter import ai_chat
from app.models.simulation import SimulationStep, Simulation

# --- Prompts ---

ARCHITECT_PROMPT = """
You are the **Simulation Architect**. Your task is to analyze the user's request and design the high-level structure of the simulation.
Do NOT generate the detailed code or prompts for every step yet. Focus on the metadata, global state, and high-level flow.

### Output Format (JSON)
{
    "name": "Simulation Name",
    "description": "Brief description",
    "variables": [
        {"key": "topic", "value": "AI Safety", "description": "The topic of debate"},
        {"key": "round", "value": "0", "description": "Current round number"}
    ],
    "agent_roles": ["Proponent", "Opponent", "Judge"],
    "flow_summary": [
        "1. Proponent states their opening argument.",
        "2. Loop 3 times: Opponent rebuts, then Proponent responds.",
        "3. Judge declares a winner."
    ]
}
"""

DEVELOPER_PROMPT = """
You are the **Simulation Developer**. Your task is to implement the detailed execution steps (JSON) based on the Architect's design and the User's request.

### Context
- **Variables**: You can use `{{state.key}}` in prompt templates.
- **File Content**: If a file was uploaded as text, its content is available in `{{state.file_content}}`.
- **Attached Files**: If the user provided files (e.g. PDFs, Images), their names are listed in the request. You can attach them to specific steps using the `files` field in the step object. Example: `"files": ["data.pdf"]`.
- **Agents**: Map the "agent_roles" to `agent_ids` (use placeholders like "agent-proponent", "agent-judge").
- **Flow**: Follow the "flow_summary" strictly.

### Step Types
1. **agent**: LLM generation. `prompt_template` is crucial.
   - `execution_mode`: "serial" or "parallel" (default). 
     - "serial": Agents in this step run one by one. Subsequent agents see the output of previous agents in the SAME step.
     - "parallel": Agents run simultaneously based on the start state.
2. **code**: Python code execution. `code_snippet` modifies `state`.
3. **loop**: Repeats `inner_steps` while a condition is true.
     - Use `loop_condition` as a **Python expression** that returns a boolean.
         Example: `state.get('i', 0) < 3 and not state.get('dialogue_ended', False)`
4. **dialogue**: Multi-turn agent-to-agent conversation within ONE step.
     - The step ends only when the dialogue ends, or the max turn cap is reached.
     - Configure with:
         - `dialogue_max_turns` (int, default 6): maximum number of alternating turns.
         - `dialogue_auto_partner` (bool, default true): if true, the initiator chooses a partner from available agents.
         - `dialogue_partner_id` (string|null): if set, initiator always talks to this partner (overrides auto selection).
         - `dialogue_end_marker` (string, default "END_DIALOGUE"): when an agent outputs this marker, the dialogue stops.
     - Use `prompt_template` as the initiator's opening instruction / topic framing.
     - Put BOTH participants in `agent_ids` only if you want to constrain who can initiate; otherwise include the initiator(s) and let the system pick partner.

### CRITICAL INSTRUCTIONS FOR JSON GENERATION
1. **NO TRUNCATION**: The output MUST be a valid, complete JSON object.
2. **CONCISENESS**: 
   - Do NOT include long comments in `code_snippet`.
   - Keep `prompt_template` effective but concise.
   - Remove unnecessary whitespace in the JSON to save tokens.
3. **ROBUSTNESS**: Ensure all JSON keys and string values are properly escaped.
4. **PYTHON CODE RULES**:
   - **NEVER** reassign `state` directly (e.g., `state = {...}`). This breaks persistence.
   - **ALWAYS** use `state.update({...})` or `state['key'] = value` to modify the state.
   - **NEVER** use dot notation for state (e.g., `state.round`). ALWAYS use `state['round']`.
   - Ensure all variables used in code are initialized in `variables` or previous steps.
5. **TEMPLATE RULES**:
   - You can use `{{state.key}}` or `{{state['key']}}` in `prompt_template`.
   - You can use `{{str(state.key)}}` or `{{int(state.key)}}` if needed.
     - `output_var` CAN contain templates (e.g., `response_{{state.round}}`) to create dynamic keys.

### IMPORTANT RUNTIME CONSTRAINTS (MUST FOLLOW)
- `agent_ids` MUST be literal strings like "agent-a". Do NOT put templates like "{{state...}}" inside `agent_ids`.

### Output Format (JSON)
{
    "steps": [
        {
            "id": "step-1",
            "type": "agent",
            "agent_ids": ["agent-proponent"],
            "prompt_template": "You are the Proponent. Argue about {{state.topic}}.",
            "output_var": "last_argument",
            "files": ["attached_doc.pdf"]
        },
        {
            "id": "step-1b",
            "type": "dialogue",
            "agent_ids": ["agent-proponent"],
            "prompt_template": "Start a conversation with another agent about {{state.topic}}. End when the discussion is complete by outputting END_DIALOGUE.",
            "dialogue_max_turns": 8,
            "dialogue_auto_partner": true,
            "dialogue_partner_id": null,
            "dialogue_end_marker": "END_DIALOGUE",
            "output_var": "dialogue_transcript"
        },
        {
            "id": "step-2",
            "type": "loop",
            "loop_condition": "state.get('i', 0) < 3",
            "inner_steps": [...]
        }
    ]
}
"""

FIXER_PROMPT = """
You are a JSON Repair Expert. The previous attempt to generate a JSON object failed or was incomplete.
Your task is to fix the JSON.

Error: <<ERROR>>
Broken JSON:
<<BROKEN_JSON>>

Return ONLY the fixed, valid JSON. Do not include markdown formatting.
"""


def _safe_token_fill(template: str, replacements: Dict[str, str]) -> str:
    out = template
    for k, v in (replacements or {}).items():
        out = out.replace(k, v)
    return out


def _extract_steps_from_developer_output(developer_output: Any) -> List[Dict[str, Any]]:
    """Best-effort normalization: return a list of step dicts from common shapes."""
    if isinstance(developer_output, list):
        # Some models output the steps list directly.
        return developer_output

    if not isinstance(developer_output, dict):
        return []

    # Common keys
    candidate_keys = [
        'steps',
        'workflow',
        'flow',
        'plan',
        'actions',
        'tasks',
        'nodes',
    ]

    for key in candidate_keys:
        v = developer_output.get(key)
        if isinstance(v, list):
            return v
        if isinstance(v, dict) and isinstance(v.get('steps'), list):
            return v.get('steps')

    # Nested containers
    for key in ['simulation', 'config', 'result', 'data', 'output']:
        v = developer_output.get(key)
        if isinstance(v, dict) and isinstance(v.get('steps'), list):
            return v.get('steps')

    return []


def _flatten_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten any loop steps into a linear list (best-effort).

    Even though the prompt asks models not to use loops, some still do.
    The front-end/run_step path is step-by-step and loop handling is limited,
    so we normalize here.
    """
    out: List[Dict[str, Any]] = []
    for s in (steps or []):
        if not isinstance(s, dict):
            continue
        if s.get('type') != 'loop':
            out.append(s)
            continue

        repeat_count = s.get('repeat_count', 1)
        try:
            repeat_count = int(repeat_count)
        except Exception:
            repeat_count = 1
        if repeat_count < 1:
            repeat_count = 1

        inner_steps = s.get('inner_steps') or []
        if not isinstance(inner_steps, list) or len(inner_steps) == 0:
            continue

        base_id = s.get('id') or 'loop'
        for i in range(repeat_count):
            for inner in inner_steps:
                if not isinstance(inner, dict):
                    continue
                inner_copy = dict(inner)
                inner_id = inner_copy.get('id') or f"{base_id}-inner"
                inner_copy['id'] = f"{base_id}-{i+1}-{inner_id}"
                out.append(inner_copy)

    return out


def _validate_steps_for_runtime(steps: List[Dict[str, Any]]) -> None:
    """Fail-fast on shapes the runtime cannot handle."""
    for s in (steps or []):
        if not isinstance(s, dict):
            continue
        st = s.get('type')
        if st in {'agent', 'dialogue'}:
            ids = s.get('agent_ids')
            if ids is None:
                continue
            if not isinstance(ids, list):
                raise ValueError('Invalid agent_ids: must be a list')
            for aid in ids:
                if isinstance(aid, str) and ('{{' in aid or '}}' in aid or '{' in aid or '}' in aid):
                    raise ValueError('Invalid agent_ids: templates are not supported in agent_ids')


def _slugify_agent_id(raw: str) -> str:
    s = (raw or '').strip().lower()
    if not s:
        return s
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9\-]", "", s)
    s = re.sub(r"\-+", "-", s).strip('-')
    return s


def _normalize_agent_ids_in_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure agent_ids are safe IDs, not display names.

    The backend runtime looks up agents by ID (AGENTS_DB key). Models sometimes
    output human names like "Agent A"; normalize to "agent-a".
    """
    for s in (steps or []):
        if not isinstance(s, dict):
            continue
        ids = s.get('agent_ids')
        if not isinstance(ids, list):
            continue
        normalized: List[str] = []
        for aid in ids:
            if not isinstance(aid, str):
                continue
            slug = _slugify_agent_id(aid)
            if slug:
                normalized.append(slug)
        if normalized:
            s['agent_ids'] = normalized
    return steps

def clean_and_parse_json(content: str):
    # Clean markdown
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    
    content = content.strip()
    
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Fallback 1: Regex
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
        
        # Fallback 2: Simple Repair (Closing brackets)
        try:
            open_braces = content.count('{')
            close_braces = content.count('}')
            open_brackets = content.count('[')
            close_brackets = content.count(']')
            
            repaired = content
            if repaired.count('"') % 2 != 0:
                repaired += '"'
            
            if open_brackets > close_brackets:
                repaired += ']' * (open_brackets - close_brackets)
            if open_braces > close_braces:
                repaired += '}' * (open_braces - close_braces)
            
            return json.loads(repaired)
        except:
            pass
            
        raise ValueError("Failed to parse JSON response")

def generate_simulation_config(
    prompt: str,
    file_content: str = None,
    file_names: List[str] = [],
    *,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generates a simulation configuration using a multi-agent (Architect -> Developer) approach.
    """
    user_content = f"User Request: {prompt}\n"
    if file_content:
        user_content += f"\nAttached File Content:\n{file_content}"
    if file_names:
        user_content += f"\nAttached Files (Available for agents): {', '.join(file_names)}"

    # --- Step 1: Architect ---
    print("--- [AI Generator] Step 1: Architect Designing... ---")
    architect_res = ai_chat(
        messages_or_prompt=[
            {"role": "system", "content": ARCHITECT_PROMPT},
            {"role": "user", "content": user_content}
        ],
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.5,
        max_tokens=2048,
        timeout_s=120.0,
    )
    
    try:
        print(f"DEBUG: Architect Raw Response (keys={list((architect_res or {}).keys())}): {str(architect_res)[:1200]}")
    except Exception:
        pass
    
    try:
        architect_design = clean_and_parse_json(architect_res.get('content', '{}'))
    except Exception as e:
        print(f"Architect failed: {e}")
        # Fallback: Empty design
        architect_design = {"name": "Generated Sim", "description": "", "variables": [], "flow_summary": []}

    print(f"Architect Design: {json.dumps(architect_design, indent=2)}")

    # --- Step 2: Developer ---
    print("--- [AI Generator] Step 2: Developer Implementing... ---")
    
    dev_context = f"""
    User Request: {prompt}
    """
    
    if file_content:
        dev_context += f"\nAttached File Content:\n{file_content}\n"
    if file_names:
        dev_context += f"\nAttached Files (Available for agents): {', '.join(file_names)}\n"
    
    dev_context += f"""
    Architect's Design:
    {json.dumps(architect_design, indent=2)}
    """
    
    developer_res = ai_chat(
        messages_or_prompt=[
            {"role": "system", "content": DEVELOPER_PROMPT},
            {"role": "user", "content": dev_context}
        ],
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.4,
        max_tokens=6144,  # Keep within typical provider limits and response time
        timeout_s=240.0,
    )
    
    try:
        print(f"DEBUG: Developer Raw Response (keys={list((developer_res or {}).keys())}): {str(developer_res)[:1200]}")
    except Exception:
        pass
    
    try:
        developer_output = clean_and_parse_json(developer_res.get('content', '{}'))
    except Exception as e:
        print(f"Developer failed: {e}. Attempting AI Fix...")
        try:
            fixer_text = _safe_token_fill(
                FIXER_PROMPT,
                {
                    '<<ERROR>>': str(e),
                    '<<BROKEN_JSON>>': (developer_res.get('content', '') or ''),
                },
            )
            fix_res = ai_chat(
                messages_or_prompt=[
                    {"role": "system", "content": fixer_text}
                ],
                model=model,
                api_key=api_key,
                base_url=base_url,
                temperature=0.1,
                max_tokens=4096,
                timeout_s=120.0,
            )
            developer_output = clean_and_parse_json(fix_res.get('content', '{}'))
            print("AI Fix Successful.")
        except Exception as e2:
            print(f"AI Fix failed: {e2}")
            developer_output = {"steps": []}

    # --- Merge ---
    steps = _extract_steps_from_developer_output(developer_output)
    steps = _normalize_agent_ids_in_steps(steps)
    _validate_steps_for_runtime(steps)

    final_config = {
        "name": architect_design.get("name", "New Simulation"),
        "description": architect_design.get("description", ""),
        "variables": architect_design.get("variables", []),
        "steps": steps
    }

    # If no steps, fail fast so callers don't end up with a broken simulation shell.
    if not isinstance(final_config.get('steps'), list) or len(final_config.get('steps')) == 0:
        raise ValueError(
            "Simulation generation returned no steps. "
            "This usually means the model output was truncated or invalid JSON, "
            "or the backend AI provider is not configured."
        )
    
    # Robustness Fix: Inject file_content if present
    if file_content:
        # Check if it's already there to avoid duplication
        existing_keys = [v.get('key') for v in final_config['variables']]
        if 'file_content' not in existing_keys:
            final_config['variables'].append({
                "key": "file_content",
                "value": file_content,
                "description": "Content of the uploaded file"
            })
    
    return final_config
