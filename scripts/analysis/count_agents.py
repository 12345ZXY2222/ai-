
import json

with open('backend/data/agents.json', 'r') as f:
    data = json.load(f)

prm_agents = [a for a in data.values() if a.get('user_id') == 'prm']
print(f"Total agents for prm: {len(prm_agents)}")
for a in prm_agents:
    print(f"- {a.get('name')}")
