
import json
import requests
from unittest.mock import MagicMock

# Mock requests
original_post = requests.post
requests.post = MagicMock()

# The code from AI_6
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
            payload["image_url"] = image_url
        
        # Prepare headers
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        print(f"DEBUG: Sending Payload: {json.dumps(payload, indent=2)}")

        # Make API request
        response = requests.post(
            base_url,
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        
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

# Setup Mock Response
mock_response = MagicMock()
mock_response.status_code = 200
mock_response.json.return_value = {"id": "12345-mock-task-id"}
requests.post.return_value = mock_response

# Execute the code to define the function
local_scope = {}
exec(code, local_scope)
invoke_custom_agent = local_scope['invoke_custom_agent']

# Simulate Input
# User Prompt: "{{state.A}} 以这个图片为首帧生成一个视频"
# Assuming state.A is an image URL
image_url = "https://example.com/image.png"
text_prompt = "以这个图片为首帧生成一个视频"

messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": text_prompt},
            {"type": "image_url", "image_url": {"url": image_url}}
        ]
    }
]

api_key = "mock_key"
base_url = "https://open.bigmodel.cn/api/paas/v4/videos/generations"
model = "cogvideox-3"

print("--- Starting Test ---")
result = invoke_custom_agent(messages, api_key, base_url, model, 0.7)
print("--- Result ---")
print(json.dumps(result, indent=2))

# Verify Payload
call_args = requests.post.call_args
if call_args:
    print("\n--- Actual Request Payload ---")
    print(json.dumps(call_args[1]['json'], indent=2))
else:
    print("No request made.")
