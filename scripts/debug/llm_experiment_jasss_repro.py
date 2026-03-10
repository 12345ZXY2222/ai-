import json
import uuid
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8001/api"
PDF_PATH = Path("backend/uploads/papers/6f21783b-6af3-4f1a-aedf-a490dfc1cc60_01_JASSS_2022_Calibrating_ABM_Innovation_Diffusion.pdf")

REQUIREMENT = (
    "请基于论文《Calibrating Agent-Based Models of Innovation Diffusion with Gradients》，"
    "把ABM中的代理决策替换为LLM代理，设计并输出可运行实验方案，"
    "要求包含可执行steps、变量、运行后分析代码和结论。"
)
QUESTION = "请给出可执行仿真与后验分析流程，并说明如何验证替代后拟合效果。"


def main() -> int:
    if not PDF_PATH.exists():
        print(f"[ERROR] PDF not found: {PDF_PATH}")
        return 2

    username = f"jasss_{uuid.uuid4().hex[:8]}"
    password = "Passw0rd!"

    reg = requests.post(f"{BASE}/register", json={"username": username, "password": password}, timeout=30)
    print("register", reg.status_code)
    if reg.status_code not in (200, 400):
        print(reg.text)
        return 1

    tok = requests.post(f"{BASE}/token", data={"username": username, "password": password}, timeout=30)
    print("token", tok.status_code)
    if tok.status_code != 200:
        print(tok.text)
        return 1

    token = tok.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with PDF_PATH.open("rb") as f:
        files = {"file": (PDF_PATH.name, f, "application/pdf")}
        up = requests.post(f"{BASE}/llm-experiments/papers/upload", files=files, headers=headers, timeout=120)
    print("upload", up.status_code)
    if up.status_code != 200:
        print(up.text)
        return 1

    paper_id = up.json()["paper_id"]
    print("paper_id", paper_id, "text_length", up.json().get("text_length"))

    solve_payload = {
        "paper_id": paper_id,
        "requirement": REQUIREMENT,
        "question": QUESTION,
        "use_web_search": False,
    }
    solve = requests.post(f"{BASE}/llm-experiments/cluster/solve", json=solve_payload, headers=headers, timeout=600)
    print("solve", solve.status_code)
    if solve.status_code != 200:
        print(solve.text)
        return 1

    solve_data = solve.json()
    plan = solve_data.get("simulation_plan") or {}
    variables = plan.get("variables") or []
    steps = plan.get("steps") or []
    print("plan steps", len(steps), "variables", len(variables), "paper_text_length", solve_data.get("paper_text_length"))

    if not steps:
        print("[ERROR] simulation_plan.steps is empty")
        return 3

    state = {}
    for v in variables:
        key = v.get("key")
        val = v.get("value", "")
        try:
            state[key] = json.loads(val)
        except Exception:
            state[key] = val

    history = []
    execute_count = min(3, len(steps))
    for index in range(execute_count):
        run_payload = {
            "steps": [steps[index]],
            "current_step_index": 0,
            "history": history,
            "world_state": state,
        }
        run = requests.post(f"{BASE}/simulation/run_step", json=run_payload, headers=headers, timeout=300)
        print("run_step", index, run.status_code)
        if run.status_code != 200:
            print(run.text)
            return 4
        body = run.json()
        history.extend(body.get("new_history_items") or [])
        state = body.get("updated_world_state") or state

    csv_text = "Step,Agent,Prompt,Files,Response\n"
    for idx, item in enumerate(history, 1):
        agent_name = str(item.get("agent_name") or "").replace('"', '""')
        prompt = str(item.get("prompt") or "").replace('"', '""')
        content = str(item.get("content") or "").replace('"', '""')
        csv_text += f'{idx},"{agent_name}","{prompt}","","{content}"\n'

    analyze_payload = {
        "paper_id": paper_id,
        "requirement": REQUIREMENT,
        "question": QUESTION,
        "simulation_plan": plan,
        "variables": variables,
        "run_history": history,
        "final_world_state": state,
        "exported_csv": csv_text,
        "analysis_code": solve_data.get("analysis_code"),
    }
    analyze = requests.post(
        f"{BASE}/llm-experiments/cluster/analyze-run",
        json=analyze_payload,
        headers=headers,
        timeout=600,
    )
    print("analyze", analyze.status_code)
    if analyze.status_code != 200:
        print(analyze.text)
        return 5

    conclusion = analyze.json().get("conclusion") or ""
    print("conclusion_length", len(conclusion))
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
