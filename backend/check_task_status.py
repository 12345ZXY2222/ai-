import json
import requests
import os

def check_status():
    # Load API Key
    with open('data/agents.json', 'r', encoding='utf-8') as f:
        agents = json.load(f)
    
    agent_id = "6a1870ec-3809-4f00-8d18-156123ccf189"
    agent = agents.get(agent_id)
    api_key = agent['api_key']
    
    # Load Task ID
    if not os.path.exists('last_task_id.txt'):
        print("Error: last_task_id.txt not found. Run test_video_generation.py first.")
        return
        
    with open('last_task_id.txt', 'r') as f:
        task_id = f.read().strip()
    
    url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    print(f"Checking status for task: {task_id}")
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    check_status()
