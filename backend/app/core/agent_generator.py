import os
from app.core.adapter import ai_chat

SYSTEM_PROMPT_TEMPLATE = """
You are an expert Python developer specializing in API integrations.
Your task is to write a Python function that adapts a specific AI model's API to a standard interface.

Target Interface:
def invoke_custom_agent(messages: list[dict], api_key: str, base_url: str, model: str, temperature: float) -> dict:
    # ... implementation ...
    # Returns a dict with keys: 'content' (str), 'reasoning_content' (str or None), 'raw' (any)
    # If ASYNC/VIDEO: Returns {'content': 'Task submitted: <id>', 'async_task_id': '<id>'}

# OPTIONAL: Only if output is video/async
def poll_custom_task(task_id: str, api_key: str, base_url: str) -> dict:
    # ... implementation ...
    # Returns {'status': 'SUCCESS', 'video_url': '...'} OR {'status': 'PROCESSING'} OR {'status': 'FAILED', 'error': '...'}

Input Information:
- Model Name: <<MODEL_NAME>>
- Base URL: <<BASE_URL>>
- Input Modality: <<INPUT_MODALITY>>
- Output Modality: <<OUTPUT_MODALITY>>
- Usage Example provided by user:
<<USAGE_EXAMPLE>>

Requirements:
1. The code must be valid Python.
2. Use `requests` or `httpx` (unless the example uses a specific SDK like `openai`).
3. Handle errors gracefully and return a dict with 'error' key.
4. **Input Handling**:
    <<INPUT_INSTRUCTIONS>>
5. **Output Handling**:
    <<OUTPUT_INSTRUCTIONS>>
6. Return the full response object in 'raw'.
7. ONLY return the Python code. Do not wrap in markdown code blocks.
8. **ASYNC/VIDEO**: You MUST generate the `poll_custom_task` function if the API is asynchronous. The backend will call this function to check status.

Specific Logic for Modalities:
- If Input is 'text_image': You MUST handle `messages` where content can be a list of dicts (e.g. `[{{'type': 'text', 'text': '...'}}, {{'type': 'image_url', ...}}]`). Extract the text for `prompt` and the URL for `image_url`.
- If Input is 'audio': You MUST handle `messages` where content includes `{{'type': 'audio_url', ...}}`. Extract the base64 data or URL.
- If Output is 'video': The API likely returns a Task ID. `invoke_custom_agent` should return `{{'content': f'Task submitted: {{task_id}}', 'async_task_id': task_id}}`. You MUST implement `poll_custom_task` to check the status using the API's polling endpoint.
- If Output is 'audio': The API might return audio content (binary) or a URL. If binary, base64 encode it and return a JSON string: `[{{"type": "audio_url", "audio_url": {{"url": "data:audio/mp3;base64,..."}}}}]`.
"""

def generate_adapter_code(model_name: str, base_url: str, usage_example: str, api_key: str | None = None, input_modality: str = "text", output_modality: str = "text") -> str:
    """
    Uses the default configured AI provider to generate adapter code.
    """
    
    input_instr = "Map `messages` to the API's expected prompt format."
    if input_modality == "text_image":
        input_instr = """
        Iterate through `messages` (reversed) to find the last user message.
        Check if `content` is a string or a list.
        If list, extract `text` parts for the prompt and `image_url` parts for the image.
        
        **CRITICAL FOR VIDEO GENERATION (Image-to-Video)**: 
        If the output is 'video', the API almost certainly requires the image to be passed in a specific parameter (e.g., 'image_url', 'image_path', 'source_image', 'ref_image_url'). 
        1. Look at the usage example to see if there is an image parameter. If not, assume 'image_url'.
        2. Extract the URL from the message content (`item['image_url']['url']`).
        3. **CRITICAL FOR LOCAL IMAGES**: The `image_url` might be a local file path (e.g. `/uploads/...` or `C:\...`). Cloud APIs cannot access local files. You MUST check if the URL is a local path. If it is local, read the file and convert it to a Base64 data URI (e.g. `data:image/png;base64,...`) before sending it to the API. Use `os.path.exists` to check. Handle `base64` encoding.
        4. Pass this (Base64 or URL) to the API's image parameter.
        5. DO NOT just append the image URL to the prompt text string, as most video models will ignore it.
        """
    elif input_modality == "audio":
        input_instr = """
        Iterate through `messages` to find audio content.
        Look for items with `type` == 'audio_url'.
        Extract the 'url' (which might be a data URI).
        If the API expects a file upload, you might need to decode the base64 data from the data URI.
        """
        
    output_instr = "Extract the response text and put it in 'content'."
    if output_modality == "image":
        output_instr = "Extract the image URL from the response and put it in 'content'. If multiple, return the first one."
    elif output_modality == "video":
        output_instr = """
        1. Extract the Task ID or Job ID from the response.
        2. Return `{'content': f"Video generation task submitted. Task ID: {task_id}", 'async_task_id': task_id, 'raw': response}`.
        3. **IMPLEMENT `poll_custom_task(task_id, api_key, base_url)`**:
           - Construct the polling URL (usually base_url + /tasks/{task_id} or similar, check usage example).
           - Make a GET request.
           - Check status (e.g. 'SUCCEEDED', 'SUCCESS', 'completed').
           - If success, extract video URL and return `{'status': 'SUCCESS', 'video_url': '...'}`.
           - If failed, return `{'status': 'FAILED', 'error': '...'}`.
           - If processing, return `{'status': 'PROCESSING'}`.
        """
    elif output_modality == "audio":
        output_instr = """
        If the API returns a URL, return it as a JSON string: `[{"type": "audio_url", "audio_url": {"url": "..."}}]`.
        If the API returns binary audio, base64 encode it and return as a data URI in the same JSON structure.
        """

    # Avoid Python `.format(...)` here because user examples/instructions often include
    # JSON/dict braces like `{'content': ...}` which would be interpreted as placeholders.
    prompt = (
        SYSTEM_PROMPT_TEMPLATE
        .replace('<<MODEL_NAME>>', str(model_name or ''))
        .replace('<<BASE_URL>>', str(base_url or 'Not specified'))
        .replace('<<INPUT_MODALITY>>', str(input_modality or 'text'))
        .replace('<<OUTPUT_MODALITY>>', str(output_modality or 'text'))
        .replace('<<USAGE_EXAMPLE>>', (usage_example or '').strip())
        .replace('<<INPUT_INSTRUCTIONS>>', (input_instr or '').strip())
        .replace('<<OUTPUT_INSTRUCTIONS>>', (output_instr or '').strip())
    )
    
    response = ai_chat(
        messages_or_prompt=[
            {"role": "system", "content": "You are a code generator. Write robust, error-handling Python code."},
            {"role": "user", "content": prompt}
        ],
        model=model_name,
        base_url=base_url,
        api_key=api_key,
        temperature=0.2,
        max_tokens=3072
    )

    if response.get('error'):
        # Avoid leaking secrets; upstream errors should not include api_key.
        raise RuntimeError(response.get('error'))
    
    content = response.get('content', '')
    if content.startswith("```python"):
        content = content[9:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
        
    return content.strip()

def fix_code_snippet(code: str, error: str) -> str:
    """
    Uses AI to fix a broken Python code snippet based on an error message.
    """
    prompt = f"""
You are an expert Python debugger.
The following code snippet failed with an error.
Please analyze the error and fix the code.

Code:
```python
{code}
```

Error:
{error}

Context:
- The code runs in a restricted scope with variables: `state` (dict), `history` (list), `json` (module).
- `state` contains the simulation world variables.
- `history` contains previous steps.

Instructions:
1. Fix the error.
2. Ensure the code is valid Python.
3. ONLY return the fixed code. Do not wrap in markdown code blocks.
4. Do not add comments explaining the fix unless necessary inside the code.
"""
    response = ai_chat(
        messages_or_prompt=[
            {"role": "system", "content": "You are a code fixer. Return only the fixed code."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=1536
    )
    
    content = response.get('content', '')
    if content.startswith("```python"):
        content = content[9:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
        
    return content.strip()
