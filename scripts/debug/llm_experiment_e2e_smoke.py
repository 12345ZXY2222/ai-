import requests, uuid, json, time

BASE = 'http://127.0.0.1:8001/api'
username = f'e2e_{uuid.uuid4().hex[:8]}'
password = 'Passw0rd!'

print('register:', username)
reg = requests.post(f'{BASE}/register', json={'username': username, 'password': password}, timeout=30)
print('register status', reg.status_code)
if reg.status_code not in (200, 400):
    print(reg.text)
    raise SystemExit(1)

tok = requests.post(f'{BASE}/token', data={'username': username, 'password': password}, timeout=30)
print('token status', tok.status_code)
if tok.status_code != 200:
    print(tok.text)
    raise SystemExit(1)

token = tok.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

search = requests.post(f'{BASE}/llm-experiments/papers/search', json={'query': 'inventory management simulation', 'max_results': 1}, headers=headers, timeout=60)
print('search status', search.status_code)
print('search body keys', list(search.json()[0].keys()) if search.status_code==200 and search.json() else [])
if search.status_code != 200 or not search.json():
    print(search.text)
    raise SystemExit(1)

paper_url = search.json()[0]['url']
title = search.json()[0]['title']
print('pull url', paper_url)
pull = requests.post(f'{BASE}/llm-experiments/papers/pull', json={'url': paper_url, 'title': title}, headers=headers, timeout=120)
print('pull status', pull.status_code)
if pull.status_code != 200:
    print(pull.text)
    raise SystemExit(1)
paper_id = pull.json()['paper_id']
print('paper id', paper_id, 'text_length', pull.json().get('text_length'))

solve_payload = {
    'paper_id': paper_id,
    'requirement': '基于论文做一个库存管理替代实验，并输出可运行仿真',
    'question': '请给出可运行且可分析的实验流程',
    'use_web_search': True,
    'top_k_sources': 2,
}
solve = requests.post(f'{BASE}/llm-experiments/cluster/solve', json=solve_payload, headers=headers, timeout=600)
print('solve status', solve.status_code)
if solve.status_code != 200:
    print(solve.text)
    raise SystemExit(1)
solve_data = solve.json()
print('solve keys', solve_data.keys())
steps = (solve_data.get('simulation_plan') or {}).get('steps') or []
variables = (solve_data.get('simulation_plan') or {}).get('variables') or []
print('steps', len(steps), 'vars', len(variables))
if not steps:
    print('empty steps')
    raise SystemExit(2)

state = {}
for v in variables:
    key = v.get('key')
    val = v.get('value', '')
    try:
        state[key] = json.loads(val)
    except Exception:
        state[key] = val
history = []

for i in range(min(2, len(steps))):
    res = requests.post(f'{BASE}/simulation/run_step', json={
        'steps': [steps[i]],
        'current_step_index': 0,
        'history': history,
        'world_state': state,
    }, headers=headers, timeout=300)
    print('run_step', i, 'status', res.status_code)
    if res.status_code != 200:
        print(res.text)
        raise SystemExit(3)
    body = res.json()
    new_items = body.get('new_history_items') or []
    if new_items:
        history.extend(new_items)
    state = body.get('updated_world_state') or state

csv_text = 'Step,Agent,Prompt,Files,Response\n'
for idx, h in enumerate(history, 1):
    csv_text += f"{idx},\"{(h.get('agent_name') or '').replace('\\\"','\\\\\\\"')}\",\"{(h.get('prompt') or '').replace('\\\"','\\\\\\\"')}\",\"\",\"{(h.get('content') or '').replace('\\\"','\\\\\\\"')}\"\\n"

an = requests.post(f'{BASE}/llm-experiments/cluster/analyze-run', json={
    'paper_id': paper_id,
    'requirement': solve_payload['requirement'],
    'question': solve_payload['question'],
    'simulation_plan': solve_data.get('simulation_plan'),
    'variables': variables,
    'run_history': history,
    'final_world_state': state,
    'exported_csv': csv_text,
    'analysis_code': solve_data.get('analysis_code'),
}, headers=headers, timeout=600)
print('analyze status', an.status_code)
if an.status_code != 200:
    print(an.text)
    raise SystemExit(4)
print('conclusion length', len(an.json().get('conclusion','')))
print('E2E SMOKE PASS')
