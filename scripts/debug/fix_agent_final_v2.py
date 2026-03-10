
import json
import os

# Absolute path to agents.json
json_path = r"c:\Users\HP\Desktop\ai模拟平台\backend\data\agents.json"

# Load agents.json
with open(json_path, 'r', encoding='utf-8') as f:
    agents = json.load(f)

# Find AI_5
agent_id = "6a1870ec-3809-4f00-8d18-156123ccf189"
if agent_id in agents:
    print("Found AI_5. Updating code...")
    
    new_code = r'''import requests
import json
import time
import re
import os

def invoke_custom_agent(messages: list[dict], api_key: str, base_url: str, model: str, temperature: float) -> dict:
    try:
        print("--- DEBUG: AI_5 Invoked (Final Fix V2) ---")
        
        prompt = ""
        img_url = ""
        base64_image = ""
        
        # 1. Parse Messages
        content_text = ""
        for message in reversed(messages):
            if message.get('role') == 'user':
                c = message.get('content')
                if isinstance(c, str):
                    content_text = c
                elif isinstance(c, list):
                    text_parts = []
                    for part in c:
                        if isinstance(part, dict):
                            if part.get('type') == 'text':
                                text_parts.append(part.get('text', ''))
                            elif part.get('type') == 'image_url':
                                # Capture Base64 if present, but don't assign to img_url yet
                                url_obj = part.get('image_url', {})
                                if isinstance(url_obj, dict):
                                    base64_image = url_obj.get('url', '')
                    content_text = "\n".join(text_parts)
                break
        
        print(f"DEBUG: Content text: {content_text}")
        
        # 2. Parse Text for Prompt and Explicit Paths
        lines = content_text.split('\n')
        implicit_lines = []
        
        for line in lines:
            clean_line = line.strip()
            if not clean_line: continue
            
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
        
        if not prompt and implicit_lines:
            prompt = "\n".join(implicit_lines)
        
        # 3. Path Detection Strategy (The Fix)
        # We prefer a local file path found in the text over a Base64 image.
        
        found_local_path = ""
        
        # Look for local path (/uploads/...)
        path_match = re.search(r'(/uploads/[^\s"\'\)\}<>]+)', content_text)
        if path_match:
            found_local_path = path_match.group(1)
            print(f"DEBUG: Found Local Path in text: {found_local_path}")
        else:
            # Look for Windows path
            win_match = re.search(r'([a-zA-Z]:\\[^\n\r"<>]+)', content_text)
            if win_match:
                found_local_path = win_match.group(1)
                print(f"DEBUG: Found Windows Path in text: {found_local_path}")

        # Decision Logic
        if img_url:
            print("DEBUG: Using explicit img_url from text.")
        elif found_local_path:
            img_url = found_local_path
            print("DEBUG: Using found local path as img_url.")
        elif base64_image:
            # Only use Base64 if no local path was found (fallback, though likely to fail for Video API)
            img_url = base64_image
            print("DEBUG: Using Base64 image (fallback).")
        
        if not prompt:
            return {'error': 'No prompt found.', 'content': '', 'reasoning_content': None, 'raw': None}
        
        # 4. Upload Logic
        # If it's a local path (not http, not file://, not data:), upload it.
        if img_url and not img_url.startswith('http') and not img_url.startswith('file://') and not img_url.startswith('data:'):
            local_path = img_url.strip('"').strip("'")
            
            # Resolve relative path
            if local_path.startswith('/uploads/'):
                # Assuming running from backend root
                local_path = local_path.lstrip('/')
            
            if not os.path.isabs(local_path):
                local_path = os.path.abspath(local_path)
            
            print(f"DEBUG: Resolving Local Path: {local_path}")
            
            if os.path.exists(local_path):
                try:
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
                except Exception as e:
                    print(f"DEBUG: Upload Exception: {e}")
            else:
                 print(f"DEBUG: Local file not found at {local_path}")

        # 5. Send Request
        headers = {
            'X-DashScope-Async': 'enable',
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        input_payload = {"prompt": prompt}
        if img_url:
            # DashScope Video usually expects 'img_url'
            input_payload["img_url"] = img_url
        
        payload = {
            "model": model,
            "input": input_payload,
            "parameters": {
                "resolution": "1280x720", 
                "duration": 5
            }
        }

        print(f"DEBUG: Sending payload: {json.dumps(payload)}")
        response = requests.post(base_url, headers=headers, json=payload)
        
        if response.status_code != 200:
            return {'error': f'API Error {response.status_code}: {response.text}', 'content': '', 'reasoning_content': None, 'raw': None}
            
        response.raise_for_status()
        result = response.json()
        
        task_id = result.get('output', {}).get('task_id', 'Unknown')
        content = f"Video generation task submitted. Task ID: {task_id}"
        
        return {
            'content': content,
            'reasoning_content': None,
            'raw': result
        }
        
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}', 'content': '', 'reasoning_content': None, 'raw': None}
'''
    
    agents[agent_id]['usage_example'] = new_code
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(agents, f, indent=2, ensure_ascii=False)
    
    print("Successfully updated AI_5 code.")
else:
    print("AI_5 not found!")
