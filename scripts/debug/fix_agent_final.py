import json
import os

file_path = 'backend/data/agents.json'

# Load agents.json
with open(file_path, 'r', encoding='utf-8') as f:
    agents = json.load(f)

# Find AI_5
agent_id = "6a1870ec-3809-4f00-8d18-156123ccf189"
if agent_id in agents:
    agent = agents[agent_id]
    
    # New code for AI_5 with MULTIMODAL SUPPORT + IMG_URL
    new_code = """import requests
import json
import time
import re
import os

def invoke_custom_agent(messages: list[dict], api_key: str, base_url: str, model: str, temperature: float) -> dict:
    try:
        print("--- DEBUG: AI_5 Invoked (Final Fix) ---")
        
        # Extract prompt and img_url from messages
        prompt = ""
        img_url = ""
        
        # Find the last user message
        content_text = ""
        
        for message in reversed(messages):
            if message.get('role') == 'user':
                c = message.get('content')
                if isinstance(c, str):
                    content_text = c
                elif isinstance(c, list):
                    # Extract text parts AND check for existing image_url parts
                    text_parts = []
                    for part in c:
                        if isinstance(part, dict):
                            if part.get('type') == 'text':
                                text_parts.append(part.get('text', ''))
                            elif part.get('type') == 'image_url':
                                # If the system already attached an image, use it!
                                url_obj = part.get('image_url', {})
                                if isinstance(url_obj, dict):
                                    found_url = url_obj.get('url', '')
                                    if found_url:
                                        img_url = found_url
                                        print(f"DEBUG: Found image_url in message list: {img_url}")
                    content_text = "\\n".join(text_parts)
                break
        
        print(f"DEBUG: Content text: {content_text}")
        
        if content_text:
            # Robust Parsing Logic
            lines = content_text.split('\\n')
            implicit_lines = []
            
            for line in lines:
                clean_line = line.strip()
                if not clean_line: continue
                
                # Check for explicit keys
                if clean_line.lower().startswith('prompt:'):
                    parts = clean_line.split(':', 1)
                    if len(parts) > 1:
                        prompt = parts[1].strip()
                elif clean_line.lower().startswith('img_url:'):
                    parts = clean_line.split(':', 1)
                    if len(parts) > 1:
                        img_url = parts[1].strip()
                else:
                    implicit_lines.append(clean_line)
            
            # If no explicit 'prompt:' was found, use the implicit lines
            if not prompt and implicit_lines:
                prompt = "\\n".join(implicit_lines)
            
            # AUTO-DETECT URL if img_url is still empty
            if not img_url:
                # 1. Look for http/https url
                url_match = re.search(r'(https?://[^\\s"\\'\\)\\}]+)', content_text)
                if url_match:
                    img_url = url_match.group(1)
                    print(f"DEBUG: Found HTTP URL in text: {img_url}")
                else:
                    # 2. Look for local path (/uploads/...)
                    # Simple regex for path starting with /uploads/
                    path_match = re.search(r'(/uploads/[^\\s"\\'\\)\\}]+)', content_text)
                    if path_match:
                        img_url = path_match.group(1)
                        print(f"DEBUG: Found Local Path in text: {img_url}")
                    else:
                        # 3. Look for Windows path
                        win_match = re.search(r'([a-zA-Z]:\\\\[^\\n\\r"]+)', content_text)
                        if win_match:
                            img_url = win_match.group(1)
                            print(f"DEBUG: Found Windows Path in text: {img_url}")

        if not prompt:
            return {'error': 'No prompt found in messages.', 'content': '', 'reasoning_content': None, 'raw': None}
        
        # --- HANDLE LOCAL FILE UPLOAD ---
        # Check if it's a local file (not http, not file://)
        if img_url and not img_url.startswith('http') and not img_url.startswith('file://') and not img_url.startswith('data:'):
            # Assume it's a local file path
            local_path = img_url.strip('"').strip("'")
            
            if local_path.startswith('/'):
                local_path = local_path.lstrip('/')
            
            if not os.path.isabs(local_path):
                local_path = os.path.abspath(local_path)
            
            print(f"DEBUG: Resolving Local Path: {local_path}")
            
            if os.path.exists(local_path):
                try:
                    # Upload to DashScope
                    upload_url = "https://dashscope.aliyuncs.com/api/v1/files"
                    upload_headers = {'Authorization': f'Bearer {api_key}'}
                    
                    file_ext = os.path.splitext(local_path)[1].lower()
                    content_type = 'image/png'
                    if file_ext in ['.jpg', '.jpeg']: content_type = 'image/jpeg'
                    elif file_ext == '.webp': content_type = 'image/webp'
                    
                    files = {'file': (os.path.basename(local_path), open(local_path, 'rb'), content_type)}
                    
                    print(f"DEBUG: Uploading {local_path} to DashScope...")
                    up_res = requests.post(upload_url, headers=upload_headers, files=files)
                    
                    if up_res.status_code == 200:
                        file_data = up_res.json()
                        file_id = file_data.get('data', {}).get('id')
                        if file_id:
                            img_url = f"file://{file_id}"
                            print(f"DEBUG: Upload successful. File ID: {img_url}")
                        else:
                            print(f"DEBUG: Upload response missing ID: {up_res.text}")
                    else:
                        print(f"DEBUG: Upload failed: {up_res.status_code} {up_res.text}")
                        # Don't return error yet, maybe the model can handle the path? (Unlikely but safe)
                except Exception as e:
                    print(f"DEBUG: Upload Exception: {e}")
            else:
                 print(f"DEBUG: Local file not found at {local_path}")

        headers = {
            'X-DashScope-Async': 'enable',
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        # Revert to 'img_url' as per user instruction
        payload = {
            "model": model,
            "input": {
                "prompt": prompt,
                "img_url": img_url if img_url else None
            },
            "parameters": {
                "resolution": "480P",
                "prompt_extend": True,
                "duration": 5,
                "audio": True
            }
        }
        
        if not img_url:
            print("DEBUG: No img_url provided in payload")
            del payload["input"]["img_url"]
        
        print(f"DEBUG: Sending payload: {json.dumps(payload)}")
        response = requests.post(base_url, headers=headers, json=payload)
        
        if response.status_code != 200:
            return {'error': f'API Error {response.status_code}: {response.text}', 'content': '', 'reasoning_content': None, 'raw': None}
            
        response.raise_for_status()
        result = response.json()
        
        content = f"Video generation task submitted. Task ID: {result.get('output', {}).get('task_id', 'Unknown')}"
        
        return {
            'content': content,
            'reasoning_content': None,
            'raw': result
        }
        
    except requests.exceptions.RequestException as e:
        return {'error': f'Request failed: {str(e)}', 'content': '', 'reasoning_content': None, 'raw': None}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}', 'content': '', 'reasoning_content': None, 'raw': None}"""

    agent['usage_example'] = new_code
    
    # Save back
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(agents, f, indent=2, ensure_ascii=False)
    
    print("Updated AI_5 code successfully with FINAL FIX.")
else:
    print("AI_5 not found.")
