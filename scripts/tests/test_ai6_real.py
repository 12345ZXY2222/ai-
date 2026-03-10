
import json
import requests
import time
import base64
import os

# --- Configuration for AI_6 ---
API_KEY = "a4e64c0e9e2846c3b92714a799797a19.Iqpj0IYns0FaVGf7"
BASE_URL = "https://open.bigmodel.cn/api/paas/v4/videos/generations"
MODEL = "cogvideox-3"

# --- The Code from AI_6 (with Base64 Fix) ---
code = """
import json
import base64
import requests
from typing import Dict, Any, Optional

def invoke_custom_agent(messages: list[dict], api_key: str, base_url: str, model: str, temperature: float) -> dict:
    try:
        # Extract prompt and image_url from messages
        prompt = ""
        image_url = None
        
        # Iterate through messages in reverse to find the last user message
        for message in reversed(messages):
            if message.get('role') == 'user':
                content = message.get('content', '')
                
                if isinstance(content, str):
                    # Simple text content
                    prompt = content
                    break
                elif isinstance(content, list):
                    # Multi-modal content with text and image
                    for item in content:
                        if isinstance(item, dict):
                            if item.get('type') == 'text':
                                prompt = item.get('text', '')
                            elif item.get('type') == 'image_url':
                                image_data = item.get('image_url', {})
                                if isinstance(image_data, dict):
                                    image_url = image_data.get('url')
                                elif isinstance(image_data, str):
                                    image_url = image_data
                    break
        
        if not prompt:
            return {
                'content': '',
                'reasoning_content': None,
                'raw': None,
                'error': 'No text prompt found in messages'
            }
        
        # Prepare request payload
        payload = {
            "model": model,
            "prompt": prompt
        }
        
        # Add image_url if available (CRITICAL for image-to-video generation)
        if image_url:
            # FIX: Handle local files by converting to Base64
            if not image_url.startswith(('http', 'https', 'data:')):
                import os
                local_path = image_url
                if local_path.startswith('/uploads/'):
                    local_path = local_path.lstrip('/')
                if os.path.exists(local_path):
                    try:
                        with open(local_path, 'rb') as f:
                            b64 = base64.b64encode(f.read()).decode('utf-8')
                            ext = os.path.splitext(local_path)[1].lower()
                            mime = 'image/png'
                            if ext in ['.jpg', '.jpeg']: mime = 'image/jpeg'
                            elif ext == '.webp': mime = 'image/webp'
                            image_url = f"data:{mime};base64,{b64}"
                    except:
                        pass
            payload["image_url"] = image_url
        
        # Prepare headers
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        print(f"DEBUG: Sending Payload to {base_url}")
        # Make API request
        response = requests.post(
            base_url,
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code != 200:
             return {
                'content': '',
                'reasoning_content': None,
                'raw': response.text,
                'error': f"API Error {response.status_code}: {response.text}"
            }

        response_data = response.json()
        
        # Extract task ID or video URL from response
        content = ""
        task_id = None
        
        # Handle different possible response structures
        if isinstance(response_data, dict):
            if 'id' in response_data:
                task_id = response_data['id']
            elif 'task_id' in response_data:
                task_id = response_data['task_id']
            elif 'job_id' in response_data:
                task_id = response_data['job_id']
            elif 'video_url' in response_data:
                content = response_data['video_url']
            elif 'url' in response_data:
                content = response_data['url']
        
        if not content and task_id:
            content = f"Video generation task submitted. Task ID: {task_id}"
        elif not content:
            # If no specific content found, use a generic success message
            content = "Video generation task submitted successfully"
        
        return {
            'content': content,
            'reasoning_content': None,  # Video models typically don't provide reasoning
            'raw': response_data,
            'async_task_id': task_id 
        }
        
    except Exception as e:
        return {
            'content': '',
            'reasoning_content': None,
            'raw': None,
            'error': f"Unexpected error: {str(e)}"
        }
"""

# --- Execute Code to get Function ---
local_scope = {}
exec(code, local_scope)
invoke_custom_agent = local_scope['invoke_custom_agent']

# --- Test Data ---
# We need a real image for Image-to-Video to work properly with CogVideoX
# Let's create a dummy small image file to test the Base64 logic
dummy_image_path = "test_image.png"
if not os.path.exists(dummy_image_path):
    # Create a simple 1x1 red pixel png
    with open(dummy_image_path, "wb") as f:
        f.write(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))

# messages = [
#     {
#         "role": "user",
#         "content": [
#             {"type": "text", "text": "让这个红色像素动起来"},
#             {"type": "image_url", "image_url": {"url": dummy_image_path}}
#         ]
#     }
# ]

# print("--- 1. Submitting Task ---")
# result = invoke_custom_agent(messages, API_KEY, BASE_URL, MODEL, 0.7)
# print("Submission Result:", json.dumps(result, indent=2))

# task_id = result.get('async_task_id')
# if not task_id:
#     print("FAILED: No Task ID returned.")
#     exit(1)

# Use the first task ID we got, which has been running for a while
task_id = "44741759974634301-8116526870615884030"

print(f"\n--- 2. Polling Task {task_id} ---")
# Simulate the Polling Logic from endpoints.py (Zhipu Fallback)
poll_url = f"https://open.bigmodel.cn/api/paas/v4/async-result/{task_id}"
headers = {"Authorization": f"Bearer {API_KEY}"}

start_time = time.time()
while time.time() - start_time < 300: # 5 mins max
    print(f"Polling {poll_url}...")
    try:
        poll_res = requests.get(poll_url, headers=headers)
        if poll_res.status_code == 200:
            task_data = poll_res.json()
            print("Poll Response:", json.dumps(task_data, indent=2))
            
            task_status = task_data.get("task_status", "")
            if task_status == "SUCCESS":
                video_result = task_data.get("video_result", [])
                if video_result: 
                    video_url = video_result[0].get("url")
                    print(f"\nSUCCESS! Video URL: {video_url}")
                    break
            elif task_status == "FAIL":
                print(f"\nFAILED: {task_data}")
                break
            else:
                print(f"Status: {task_status}. Waiting...")
        else:
            print(f"Poll Error: {poll_res.status_code} {poll_res.text}")
            
        time.sleep(5)
    except Exception as e:
        print(f"Exception: {e}")
        time.sleep(5)

