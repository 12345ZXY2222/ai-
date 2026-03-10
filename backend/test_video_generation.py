import json
import os
import sys
import base64

# Ensure we are in the backend directory for path resolution to work as expected
if not os.getcwd().endswith('backend'):
    print("Please run this script from the 'backend' directory.")
    sys.exit(1)

def test_ai_5():
    print("Loading agents.json...")
    with open('data/agents.json', 'r', encoding='utf-8') as f:
        agents = json.load(f)

    agent_id = "6a1870ec-3809-4f00-8d18-156123ccf189"
    agent = agents.get(agent_id)
    
    if not agent:
        print("AI_5 not found!")
        return

    print(f"Found Agent: {agent['name']}")
    
    # Extract configuration
    api_key = agent['api_key']
    base_url = agent['base_url']
    model = agent['model']
    code = agent['usage_example']
    
    # Load the custom function
    local_scope = {}
    exec(code, local_scope)
    invoke_custom_agent = local_scope['invoke_custom_agent']
    
    # Simulate the Input
    # Use Base64 for testing
    test_image_rel = "uploads/generated/5f2dd800-21d6-4a0e-92c9-a90cab0c218b.png"
    test_image_abs = os.path.abspath(test_image_rel)
    
    if not os.path.exists(test_image_abs):
        print(f"Error: Test image not found at {test_image_abs}")
        return

    with open(test_image_abs, "rb") as image_file:
        base64_data = base64.b64encode(image_file.read()).decode('utf-8')
        base64_url = f"data:image/png;base64,{base64_data}"

    prompt_text = f"img_url: {base64_url}\n以这个图片为首帧生成一个视频"
    
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt_text
                }
            ]
        }
    ]
    
    print("\n--- Invoking Agent ---")
    print(f"Prompt: {prompt_text[:100]}...")
    
    try:
        result = invoke_custom_agent(
            messages=messages,
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=0.5
        )
        
        print("\n--- Result ---")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Save the task ID to a file for the check script
        if result and 'content' in result and 'Task ID: ' in result['content']:
            task_id = result['content'].split('Task ID: ')[1].strip()
            with open('last_task_id.txt', 'w') as f:
                f.write(task_id)
            print(f"Task ID saved to last_task_id.txt: {task_id}")
        
    except Exception as e:
        print(f"\n--- Error ---")
        print(e)

if __name__ == "__main__":
    test_ai_5()
