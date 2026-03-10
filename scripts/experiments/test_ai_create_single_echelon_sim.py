#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


@dataclass
class Auth:
    base_url: str
    username: str
    password: str
    token: str


def _post_json(session: requests.Session, url: str, payload: Dict[str, Any], timeout: float = 60.0) -> Dict[str, Any]:
    r = session.post(url, json=payload, timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"POST {url} failed: {r.status_code} {r.text}")
    return r.json()


def _get_json(session: requests.Session, url: str, timeout: float = 30.0) -> Any:
    r = session.get(url, timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"GET {url} failed: {r.status_code} {r.text}")
    return r.json()


def register_and_login(base_url: str, username: str, password: str) -> Auth:
    session = requests.Session()

    # Register (idempotent-ish: if already exists, continue to login)
    reg_url = f"{base_url}/register"
    try:
        _post_json(session, reg_url, {"username": username, "password": password})
    except Exception as e:
        # If user exists, register returns 400; that's OK.
        if "already" not in str(e).lower() and "registered" not in str(e).lower() and "400" not in str(e):
            raise

    token_url = f"{base_url}/token"
    r = session.post(
        token_url,
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Login failed: {r.status_code} {r.text}")
    data = r.json()
    token = data["access_token"]

    authed = requests.Session()
    authed.headers.update({"Authorization": f"Bearer {token}"})
    return Auth(base_url=base_url, username=username, password=password, token=token)


def ensure_template_agent(auth: Auth, provider: str, model: str, base_url: Optional[str], api_key: Optional[str]) -> Dict[str, Any]:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth.token}"})

    agents = _get_json(s, f"{auth.base_url}/agents")
    if agents:
        return agents[0]

    payload: Dict[str, Any] = {
        "name": "Template Agent",
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
        "persona": "You are a helpful assistant for inventory management experiments.",
        "long_term_memory": [],
    }
    created = _post_json(s, f"{auth.base_url}/agents", payload)
    return created


def upload_temp_file(auth: Auth, file_path: Path) -> str:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth.token}"})
    url = f"{auth.base_url}/simulations/upload_temp"
    with file_path.open("rb") as f:
        r = s.post(url, files={"file": (file_path.name, f)}, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"Upload failed: {r.status_code} {r.text}")
    return r.json()["filename"]


def generate_simulation(auth: Auth, prompt: str, file_names: List[str]) -> Dict[str, Any]:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth.token}"})
    url = f"{auth.base_url}/simulations/generate"
    r = s.post(url, json={"prompt": prompt, "file_content": None, "file_names": file_names}, timeout=900)
    if r.status_code >= 400:
        raise RuntimeError(f"Generate simulation failed: {r.status_code} {r.text}")
    return r.json()


def save_simulation(auth: Auth, sim: Dict[str, Any]) -> Dict[str, Any]:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth.token}"})
    url = f"{auth.base_url}/simulations"
    payload = {
        "name": sim.get("name") or "Generated Simulation",
        "description": sim.get("description") or "",
        "steps": sim.get("steps") or [],
        "variables": sim.get("variables") or [],
    }
    r = s.post(url, json=payload, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"Save simulation failed: {r.status_code} {r.text}")
    return r.json()


def run_simulation_step(auth: Auth, step: Dict[str, Any], history: List[Dict[str, Any]], world_state: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth.token}"})
    url = f"{auth.base_url}/simulation/run_step"
    payload = {
        "steps": [step],
        "current_step_index": 0,
        "history": history,
        "world_state": world_state,
    }
    r = s.post(url, json=payload, timeout=900)
    if r.status_code >= 400:
        raise RuntimeError(f"Run step failed: {r.status_code} {r.text}")
    data = r.json()
    return data.get("new_history_items", []), data.get("updated_world_state", {})


def _init_world_state(variables: List[Dict[str, Any]]) -> Dict[str, Any]:
    state: Dict[str, Any] = {}
    for v in variables:
        k = v.get("key")
        raw = v.get("value", "")
        if not k:
            continue
        try:
            state[k] = json.loads(raw)
        except Exception:
            state[k] = raw
    return state


def _resolve_repeat_count(repeat_count: Any, state: Dict[str, Any]) -> int:
    if repeat_count is None:
        return 1
    if isinstance(repeat_count, int):
        return max(0, repeat_count)
    if isinstance(repeat_count, str):
        s = repeat_count.strip()
        if s.startswith("{{state.") and s.endswith("}}"):
            key = s[len("{{state.") : -2]
            val = state.get(key)
            try:
                return max(0, int(val))
            except Exception:
                return 1
        try:
            return max(0, int(s))
        except Exception:
            return 1
    return 1


def execute_simulation(auth: Auth, sim: Dict[str, Any], max_steps: int = 5000) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = sim.get("steps") or []
    variables: List[Dict[str, Any]] = sim.get("variables") or []

    history: List[Dict[str, Any]] = []
    world_state: Dict[str, Any] = _init_world_state(variables)

    # Stack of frames for loop/repeat expansion (mimics frontend SimulationContext)
    stack: List[Dict[str, Any]] = [{"steps": steps, "index": 0}]

    executed = 0
    while stack:
        if executed >= max_steps:
            raise RuntimeError(f"Aborting: exceeded max_steps={max_steps}")

        frame = stack[-1]
        if frame["index"] >= len(frame["steps"]):
            stack.pop()
            continue

        step = frame["steps"][frame["index"]]

        repeat_count = _resolve_repeat_count(step.get("repeat_count"), world_state)
        if repeat_count == 0:
            frame["index"] += 1
            continue

        if repeat_count > 1:
            repeated = []
            for _ in range(repeat_count):
                copied = dict(step)
                copied["repeat_count"] = 1
                repeated.append(copied)
            frame["index"] += 1
            stack.append({"steps": repeated, "index": 0})
            continue

        if step.get("type") == "loop":
            is_true = True
            cond = (step.get("loop_condition") or "").strip()
            if cond:
                eval_step = {
                    "id": "temp-eval",
                    "type": "code",
                    "code_snippet": f"state['__loop_result'] = {cond}",
                }
                new_items, new_state = run_simulation_step(auth, eval_step, [], world_state)
                # crude error detection
                if new_items and isinstance(new_items[0].get("content"), str) and new_items[0]["content"].startswith("Error"):
                    raise RuntimeError(f"Loop condition error: {new_items[0]['content']}")
                is_true = bool(new_state.get("__loop_result"))
                if "__loop_result" in new_state:
                    del new_state["__loop_result"]
                world_state = new_state

            if is_true:
                stack.append({"steps": step.get("inner_steps") or [], "index": 0})
            else:
                frame["index"] += 1
            continue

        # Normal step execution
        new_items, new_state = run_simulation_step(auth, step, history, world_state)
        history.extend(new_items)
        world_state = new_state
        frame["index"] += 1
        executed += 1

    return {"history": history, "final_world_state": world_state, "executed_steps": executed}


def build_prompt() -> str:
    return """
请你根据我提供的参考文献与实验设想，为【单级动态库存（Single Echelon / Lost Sales）】创建一个可直接运行的 Simulation。

硬性要求（必须满足，否则算失败）：
1) Simulation 需要能够完整跑完 15 个周期（Period 1..15）。
2) 每个周期都必须：
   - 生成需求 demand_t ~ Poisson(lam=5)
   - 接收在途到货 arrived = pipeline.pop(0)
   - 更新净库存 net_inv
   - Lost Sales：sales = min(net_inv, demand_t)，lost_sales = demand_t - sales，净库存不能为负
   - 由 AI 作为“库存经理”决策订货量 order_quantity（整数，>=0），并 pipeline.append(order_quantity)
3) 初始条件与参数：
   - 提前期 L=4
   - 持有成本 h=1
   - 丢失销售惩罚 p=9
   - lam=5（注意：变量名必须是 lam，不要用 lambda）
   - rounds=15
   - 初始净库存 net_inv=20
   - 初始在途 pipeline=[5,5,5,5]
4) 必须在每期把关键变量写入 state（用于后续分析），每期都要更新这些顶层字段：
   - period, demand, arrived, sales, net_inv, pipeline, ip, order_quantity, period_cost, total_cost
   - ip = net_inv + sum(pipeline)
   - period_cost = h*net_inv + p*lost_sales
5) AI 决策必须使用“临界比率 + 目标S + IP + Q”的结构：
   - CR = p/(p+h)
   - L+1 个周期总需求分布：Poisson(lambda_total = lam*(L+1))
   - S 为满足分位数 CR 的最小整数
   - Q = max(0, S - IP)

执行环境约束（必须遵守）：
- 代码 step 的执行环境每步都是全新 exec，不会共享 import；凡是用到的模块都必须在该 code_snippet 内 import。
- 禁止依赖 scipy（环境可能没有）；如果要算 Poisson 分位数，请用纯 Python（math/循环）实现。

输出格式要求：
- AI 的输出必须是严格 JSON，且只能包含字段: reasoning（字符串）与 order_quantity（非负整数）。
- Simulation 的 variables 必须包含：L,h,p,lam,rounds,period,net_inv,pipeline,total_cost,CR,S。

请把 Simulation 命名为："Single Echelon Lost Sales (LLM)"
描述里写清楚这是基于文献设想的 15 期动态库存控制实验。
""".strip()


def _ensure_var(variables: List[Dict[str, Any]], key: str, value: Any, description: str) -> None:
    for v in variables:
        if v.get("key") == key:
            v["value"] = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
            if description and not v.get("description"):
                v["description"] = description
            return
    variables.append(
        {
            "key": key,
            "value": json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value,
            "description": description,
        }
    )


def postprocess_single_echelon_sim(sim: Dict[str, Any], agent_id: str) -> Dict[str, Any]:
    """Repair AI-created simulation into an executable, spec-compliant baseline.

    Why: The backend runs each code step with `exec(..., {}, local_scope)` so imports do not persist.
    Also SciPy may be unavailable; and agent_ids must match an existing Agent id.
    """

    sim = dict(sim)
    sim["name"] = "Single Echelon Lost Sales (LLM)"
    sim["description"] = (
        sim.get("description")
        or "A 15-period dynamic inventory control simulation for a single-echelon lost-sales system."
    )

    variables: List[Dict[str, Any]] = list(sim.get("variables") or [])
    # Normalize lam naming: keep `lam`, avoid reserved word `lambda`.
    lambda_val = None
    for v in variables:
        if v.get("key") == "lambda":
            try:
                lambda_val = json.loads(v.get("value", "5"))
            except Exception:
                lambda_val = v.get("value")
    variables = [v for v in variables if v.get("key") != "lambda"]

    _ensure_var(variables, "L", 4, "Lead time (periods)")
    _ensure_var(variables, "h", 1, "Holding cost per unit per period")
    _ensure_var(variables, "p", 9, "Lost sales penalty per unit")
    _ensure_var(variables, "lam", int(lambda_val) if lambda_val is not None else 5, "Mean demand per period (Poisson)")
    _ensure_var(variables, "rounds", 15, "Total number of periods to simulate")
    _ensure_var(variables, "period", 0, "Current period")
    _ensure_var(variables, "net_inv", 20, "Initial net inventory")
    _ensure_var(variables, "pipeline", [5, 5, 5, 5], "Initial pipeline")
    _ensure_var(variables, "total_cost", 0.0, "Cumulative total cost")
    _ensure_var(variables, "CR", 0.9, "Critical ratio p/(p+h)")
    _ensure_var(variables, "S", None, "Target base-stock level")

    sim["variables"] = variables

    init_code = """
import math

def poisson_cdf(k: int, mean: float) -> float:
    if k < 0:
        return 0.0
    p0 = math.exp(-mean)
    cdf = p0
    p = p0
    for i in range(1, k + 1):
        p = p * mean / i
        cdf += p
    return cdf

def poisson_quantile(cr: float, mean: float, k_max: int = 500) -> int:
    if cr <= 0:
        return 0
    if cr >= 1:
        # Use a conservative upper bound
        cr = 0.999999
    for k in range(0, k_max + 1):
        if poisson_cdf(k, mean) >= cr:
            return k
    return k_max

state['L'] = int(state.get('L', 4))
state['h'] = float(state.get('h', 1))
state['p'] = float(state.get('p', 9))
state['lam'] = float(state.get('lam', 5))
state['rounds'] = int(state.get('rounds', 15))
state['period'] = int(state.get('period', 0))
state['net_inv'] = int(state.get('net_inv', 20))
state['pipeline'] = list(state.get('pipeline', [5,5,5,5]))
state['total_cost'] = float(state.get('total_cost', 0.0))

state['CR'] = state['p'] / (state['p'] + state['h'])
lambda_total = state['lam'] * (state['L'] + 1)
state['S'] = poisson_quantile(state['CR'], lambda_total)

state.setdefault('history', [])

# Initialize required per-period top-level fields
state['demand'] = None
state['arrived'] = None
state['sales'] = None
state['ip'] = state['net_inv'] + sum(state['pipeline'])
state['order_quantity'] = None
state['period_cost'] = 0.0

state['history'].append({
    'period': state['period'],
    'demand': state['demand'],
    'arrived': state['arrived'],
    'sales': state['sales'],
    'net_inv': state['net_inv'],
    'pipeline': list(state['pipeline']),
    'ip': state['ip'],
    'order_quantity': state['order_quantity'],
    'period_cost': state['period_cost'],
    'total_cost': state['total_cost'],
})
""".strip()

    period_update_code = """
import math
import random

def poisson_sample(lam: float) -> int:
    # Knuth algorithm; good enough for lam~5.
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1

state['period'] = int(state.get('period', 0)) + 1

demand_t = poisson_sample(float(state.get('lam', 5)))
pipeline = list(state.get('pipeline') or [])
arrived = int(pipeline.pop(0)) if pipeline else 0

net_inv = int(state.get('net_inv', 0)) + arrived
sales = min(net_inv, demand_t)
lost_sales = demand_t - sales
net_inv = net_inv - sales
if net_inv < 0:
    net_inv = 0

h = float(state.get('h', 1))
p = float(state.get('p', 9))
period_cost = h * net_inv + p * lost_sales
total_cost = float(state.get('total_cost', 0.0)) + period_cost

state['demand'] = int(demand_t)
state['arrived'] = int(arrived)
state['sales'] = int(sales)
state['net_inv'] = int(net_inv)
state['pipeline'] = pipeline
state['period_cost'] = float(period_cost)
state['total_cost'] = float(total_cost)
state['ip'] = int(state['net_inv'] + sum(state['pipeline']))

# Provide event summary for agent prompt
state['current_demand'] = state['demand']
state['current_arrived'] = state['arrived']
state['current_sales'] = state['sales']
state['current_lost_sales'] = int(lost_sales)
state['current_period_cost'] = state['period_cost']
""".strip()

    agent_prompt = """
You are the Inventory Manager for a single-echelon lost-sales system.

CURRENT PERIOD: {{state['period']}} of {{state['rounds']}}

INVENTORY STATUS:
- Net Inventory: {{state['net_inv']}} units
- Pipeline (orders in transit): {{state['pipeline']}}
- Inventory Position (IP) = {{state['ip']}}

THIS PERIOD'S EVENTS:
- Demand: {{state['current_demand']}} units
- Arrived shipment: {{state['current_arrived']}} units
- Sales: {{state['current_sales']}} units
- Lost Sales: {{state['current_lost_sales']}} units
- Period Cost: {{state['current_period_cost']}}

POLICY PARAMETERS:
- L={{state['L']}}, h={{state['h']}}, p={{state['p']}}, lam={{state['lam']}}
- CR = p/(p+h) = {{state['CR']}}
- Target base-stock level S = {{state['S']}}

DECISION RULE:
Q = max(0, S - IP)

OUTPUT REQUIREMENTS:
Respond with STRICT JSON ONLY (no markdown, no extra keys):
{"reasoning": "...", "order_quantity": 0}
""".strip()

    process_order_code = """
import json

decision = state.get('agent_decision')
decision = extract_json(decision)

suggested_q = max(0, int(state.get('S', 0)) - int(state.get('ip', 0)))

order_qty = None
reasoning = ""
if isinstance(decision, dict):
    order_qty = decision.get('order_quantity')
    reasoning = decision.get('reasoning', '')

try:
    if order_qty is None:
        raise ValueError('no order_quantity')
    order_qty = int(order_qty)
    if order_qty < 0:
        order_qty = 0
except Exception:
    order_qty = int(suggested_q)
    reasoning = (reasoning or '').strip() or f"Fallback to policy Q=max(0,S-IP)={order_qty}."

pipeline = list(state.get('pipeline') or [])
pipeline.append(order_qty)
state['pipeline'] = pipeline
state['order_quantity'] = int(order_qty)
state['ip'] = int(state.get('net_inv', 0) + sum(state['pipeline']))

state.setdefault('history', [])
state['history'].append({
    'period': int(state.get('period', 0)),
    'demand': int(state.get('demand', 0)),
    'arrived': int(state.get('arrived', 0)),
    'sales': int(state.get('sales', 0)),
    'net_inv': int(state.get('net_inv', 0)),
    'pipeline': list(state.get('pipeline') or []),
    'ip': int(state.get('ip', 0)),
    'order_quantity': int(state.get('order_quantity', 0)),
    'order_reasoning': reasoning,
    'period_cost': float(state.get('period_cost', 0.0)),
    'total_cost': float(state.get('total_cost', 0.0)),
})

# cleanup
for k in ['current_demand','current_arrived','current_sales','current_lost_sales','current_period_cost']:
    if k in state:
        del state[k]
""".strip()

    final_summary_code = """
history = list(state.get('history') or [])
period_rows = [h for h in history if isinstance(h, dict) and h.get('period') not in (None, 0)]

total_demand = sum(int(r.get('demand', 0)) for r in period_rows)
total_sales = sum(int(r.get('sales', 0)) for r in period_rows)
total_lost = sum(int(r.get('demand', 0)) - int(r.get('sales', 0)) for r in period_rows)
service_level = (total_sales / total_demand) if total_demand > 0 else 0.0
avg_inv = (sum(int(r.get('net_inv', 0)) for r in period_rows) / len(period_rows)) if period_rows else 0.0
avg_cost = (sum(float(r.get('period_cost', 0.0)) for r in period_rows) / len(period_rows)) if period_rows else 0.0

state['final_statistics'] = {
    'total_periods': int(state.get('period', 0)),
    'total_demand': int(total_demand),
    'total_sales': int(total_sales),
    'total_lost_sales': int(total_lost),
    'service_level': float(service_level),
    'average_inventory': float(avg_inv),
    'total_cost': float(state.get('total_cost', 0.0)),
    'average_period_cost': float(avg_cost),
    'final_net_inventory': int(state.get('net_inv', 0)),
    'final_pipeline': list(state.get('pipeline') or []),
}
""".strip()

    repaired_steps: List[Dict[str, Any]] = [
        {
            "id": "step-init",
            "type": "code",
            "code_snippet": init_code,
            "repeat_count": 1,
            "output_format": "raw",
        },
        {
            "id": "step-loop",
            "type": "loop",
            "loop_condition": "state['period'] < state['rounds']",
            "inner_steps": [
                {
                    "id": "step-period-update",
                    "type": "code",
                    "code_snippet": period_update_code,
                    "repeat_count": 1,
                    "output_format": "raw",
                },
                {
                    "id": "step-agent-decision",
                    "type": "agent",
                    "agent_ids": [agent_id],
                    "prompt_template": agent_prompt,
                    "output_var": "agent_decision",
                    "execution_mode": "serial",
                    "output_format": "raw",
                },
                {
                    "id": "step-process-order",
                    "type": "code",
                    "code_snippet": process_order_code,
                    "repeat_count": 1,
                    "output_format": "raw",
                },
            ],
        },
        {
            "id": "step-final-summary",
            "type": "code",
            "code_snippet": final_summary_code,
            "repeat_count": 1,
            "output_format": "raw",
        },
    ]

    sim["steps"] = repaired_steps
    return sim


def quality_report(sim: Dict[str, Any], run: Dict[str, Any]) -> str:
    steps = sim.get("steps") or []
    variables = sim.get("variables") or []

    final_state = run.get("final_world_state") or {}

    checks: List[str] = []
    checks.append(f"steps={len(steps)} variables={len(variables)} executed_steps={run.get('executed_steps')}")

    # Flag runtime errors early
    errors = []
    for item in run.get("history") or []:
        c = item.get("content")
        if isinstance(c, str) and (c.startswith("Error executing code:") or c.startswith("Error:")):
            errors.append(c)
    if errors:
        checks.append(f"runtime_errors={len(errors)}")

    needed_vars = ["L", "h", "p", "lam", "rounds", "net_inv", "pipeline"]
    missing = [v for v in needed_vars if v not in {x.get('key') for x in variables if isinstance(x, dict)}]
    if missing:
        checks.append(f"missing_initial_variables={missing}")

    # State keys expected after run
    expected_state_keys = [
        "period",
        "demand",
        "arrived",
        "sales",
        "net_inv",
        "pipeline",
        "ip",
        "order_quantity",
        "period_cost",
        "total_cost",
    ]
    missing_state = [k for k in expected_state_keys if k not in final_state]
    if missing_state:
        checks.append(f"missing_final_state_keys={missing_state}")

    # Basic sanity
    try:
        pipeline = final_state.get("pipeline")
        if isinstance(pipeline, list):
            if any((not isinstance(x, (int, float))) for x in pipeline):
                checks.append("pipeline_non_numeric")
        else:
            checks.append("pipeline_not_list")
    except Exception:
        checks.append("pipeline_check_failed")

    return "\n".join(checks)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=os.environ.get("AISIM_API", "http://127.0.0.1:8001/api"))
    ap.add_argument("--provider", default=os.environ.get("AISIM_PROVIDER", "deepseek"))
    ap.add_argument("--model", default=os.environ.get("AISIM_MODEL", "deepseek-reasoner"))
    ap.add_argument("--base-url", dest="base_url", default=os.environ.get("AISIM_LLM_BASE_URL"))
    ap.add_argument("--api-key", dest="api_key", default=os.environ.get("AISIM_LLM_API_KEY"))
    ap.add_argument("--ref", default=str(Path("论文/库存管理的比较/gijsbrechts-et-al-2022-can-deep-reinforcement-learning-improve-inventory-management-performance-on-lost-sales-dual.pdf")))
    ap.add_argument("--username", default=os.environ.get("AISIM_USER"))
    ap.add_argument("--password", default=os.environ.get("AISIM_PASS"))
    ap.add_argument("--save-artifacts", action="store_true")
    args = ap.parse_args()

    username = args.username or f"inv_test_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    password = args.password or f"pw_{uuid.uuid4().hex}"

    auth = register_and_login(args.api, username, password)
    agent = ensure_template_agent(auth, args.provider, args.model, args.base_url, args.api_key)

    ref_path = Path(args.ref)
    file_names: List[str] = []
    if ref_path.exists():
        fname = upload_temp_file(auth, ref_path)
        file_names.append(fname)
    else:
        print(f"WARN: reference file not found: {ref_path}")

    prompt = build_prompt()
    sim = generate_simulation(auth, prompt, file_names)

    # Repair generated simulation to ensure it is executable and meets hard requirements.
    sim = postprocess_single_echelon_sim(sim, agent_id=agent.get("id"))
    saved = save_simulation(auth, sim)

    run = execute_simulation(auth, sim)
    report = quality_report(sim, run)

    print("\n=== Generated Simulation (Summary) ===")
    print(f"name={sim.get('name')} saved_id={saved.get('id')} user={username}")
    print(report)

    if args.save_artifacts:
        out_dir = Path("artifacts/results/json")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "single_echelon_generated_sim.json").write_text(json.dumps(sim, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "single_echelon_generated_run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Artifacts written to {out_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
