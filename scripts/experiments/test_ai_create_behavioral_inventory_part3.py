#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""端到端测试：用 AI Create 基于“行为库存管理”报告/文献生成 simulation，并执行+评估质量。

说明：
- 先选最小可行的一个实验：Newsvendor pull-to-center + 去偏处理（Choice activity）。
- 把报告与若干关键参考文献作为 files 上传给 /simulations/generate（后端会抽取文本）。
- 生成后：保存 simulation，并执行（包含 loop 展开），最后输出质量报告并保存 artifacts。

用法示例：
  python scripts/experiments/test_ai_create_behavioral_inventory_part3.py --save-artifacts

可选参数：
  --base-url http://127.0.0.1:8001
  --provider deepseek --model deepseek-chat
  --include-refs 1
"""

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

    # Register (idempotent-ish)
    reg_url = f"{base_url}/api/register"
    try:
        _post_json(session, reg_url, {"username": username, "password": password})
    except Exception as e:
        if "already" not in str(e).lower() and "registered" not in str(e).lower() and "400" not in str(e):
            raise

    token_url = f"{base_url}/api/token"
    r = session.post(
        token_url,
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Login failed: {r.status_code} {r.text}")
    token = r.json()["access_token"]

    return Auth(base_url=base_url, username=username, password=password, token=token)


def ensure_template_agent(auth: Auth, provider: str, model: str, base_url: Optional[str], api_key: Optional[str]) -> Dict[str, Any]:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth.token}"})

    agents = _get_json(s, f"{auth.base_url}/api/agents")
    if agents:
        return agents[0]

    payload: Dict[str, Any] = {
        "name": "Template Agent",
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
        "persona": "你是一个用于行为运营/库存管理实验的AI被试（silicon subject）。",
        "long_term_memory": [],
    }
    return _post_json(s, f"{auth.base_url}/api/agents", payload)


def upload_temp_file(auth: Auth, file_path: Path) -> str:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth.token}"})
    url = f"{auth.base_url}/api/simulations/upload_temp"
    with file_path.open("rb") as f:
        r = s.post(url, files={"file": (file_path.name, f)}, timeout=240)
    if r.status_code >= 400:
        raise RuntimeError(f"Upload failed: {r.status_code} {r.text}")
    return r.json()["filename"]


def generate_simulation(auth: Auth, prompt: str, file_names: List[str]) -> Dict[str, Any]:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth.token}"})
    url = f"{auth.base_url}/api/simulations/generate"
    r = s.post(url, json={"prompt": prompt, "file_content": None, "file_names": file_names}, timeout=1200)
    if r.status_code >= 400:
        raise RuntimeError(f"Generate simulation failed: {r.status_code} {r.text}")
    return r.json()


def save_simulation(auth: Auth, sim: Dict[str, Any]) -> Dict[str, Any]:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth.token}"})
    url = f"{auth.base_url}/api/simulations"
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
    url = f"{auth.base_url}/api/simulation/run_step"
    payload = {
        "steps": [step],
        "current_step_index": 0,
        "history": history,
        "world_state": world_state,
    }
    r = s.post(url, json=payload, timeout=1200)
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
            try:
                return max(0, int(state.get(key)))
            except Exception:
                return 1
        try:
            return max(0, int(s))
        except Exception:
            return 1
    return 1


def execute_simulation(auth: Auth, sim: Dict[str, Any], max_steps: int = 8000) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = sim.get("steps") or []
    variables: List[Dict[str, Any]] = sim.get("variables") or []

    history: List[Dict[str, Any]] = []
    world_state: Dict[str, Any] = _init_world_state(variables)

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

        new_items, new_state = run_simulation_step(auth, step, history, world_state)
        history.extend(new_items)
        world_state = new_state
        frame["index"] += 1
        executed += 1

    return {"history": history, "final_world_state": world_state, "executed_steps": executed}


def _count_runtime_errors(history: List[Dict[str, Any]]) -> int:
    n = 0
    for h in history:
        c = h.get("content")
        if isinstance(c, str) and (c.startswith("Error executing code") or c.startswith("Error:")):
            n += 1
    return n


def _extract_history_records(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    hist = state.get("history")
    return hist if isinstance(hist, list) else []


def quality_report(sim: Dict[str, Any], run: Dict[str, Any]) -> Dict[str, Any]:
    steps = sim.get("steps") or []
    variables = sim.get("variables") or []
    history = run.get("history") or []
    final_state = run.get("final_world_state") or {}

    records = _extract_history_records(final_state)

    # Heuristics for this experiment:
    # - should have multiple scenarios (profit/high-low) and multiple replications
    # - should include fields we can analyze: demand, order, profit/cost, optimal order (or enough to compute)
    report = {
        "steps": len(steps),
        "variables": len(variables),
        "executed_steps": run.get("executed_steps"),
        "runtime_errors": _count_runtime_errors(history),
        "final_state_keys": sorted(list(final_state.keys()))[:80],
        "history_records": len(records),
        "has_scenarios": any(isinstance(r, dict) and ("scenario" in r or "treatment" in r) for r in records),
        "has_orders": any(isinstance(r, dict) and ("order_quantity" in r or "order" in r or "Q" in r) for r in records),
        "has_demands": any(isinstance(r, dict) and ("demand" in r or "demand_t" in r) for r in records),
    }
    return report


def build_prompt(agent_id: str) -> str:
    # 这个 prompt 直接对应阅读报告里“2.1 Choice activity：Newsvendor pull-to-center + 去偏处理”的实验方向
    return f"""
你是实验架构师，请根据我给你的“行为库存管理”阅读报告与参考文献，生成一个可运行的 Simulation，
用于复现/检验 LLM 在 Newsvendor 报童订货中的 Pull-to-Center 偏差，并加入去偏（debiasing）处理。

实验目标（必须落地到可运行仿真，而不是只写说明）：
- 在不同利润条件（高缺货罚损 vs 低缺货罚损，或等价的不同 critical ratio）下，让 LLM 作为订货决策者选择订货量 Q。
- 记录并分析是否出现 pull-to-center：
  - 高利润情景下 Q 偏低（低于最优 Q*）
  - 低利润情景下 Q 偏高（高于最优 Q*）
- 设置至少两类 treatment：
  1) Baseline（不额外提示）
  2) Debias（加入培训/反馈/解释要求等，参考 Schweitzer & Cachon 2000、Bostian et al. 2008 的描述）

仿真设计（硬性要求）：
1) 至少包含 2 个 profit 条件（比如 CR=0.2 与 CR=0.8，或用 c_u/c_o 映射）。
2) 每个条件下至少重复 30 次独立轮次（replications），每次是单周期 newsvendor（单次订货后 realize demand）。
3) 需求分布必须是“已知分布”（例如 Poisson 或 Normal），并且 simulation 内要能计算最优订货量 Q*（用分位数）。
4) 每次轮次都要保存记录到 state['history']（list of dict），至少包含：
   - treatment / scenario 标识
   - critical_ratio 或利润参数
   - demand
   - order_quantity (LLM 决策)
   - optimal_order (Q*)
   - profit 或 cost
   - deviation = order_quantity - optimal_order
5) 运行结束后给出汇总统计（按 treatment 与 scenario 分组）：
   - 平均 deviation
   - pull-to-center 指标（例如 sign 是否符合偏差定义）

平台约束（必须遵守，否则运行会报错）：
- 禁止依赖 scipy。
- 每个 code step 必须在自己 snippet 里 import 需要的标准库（math/random/statistics 等）。
- agent step 必须严格输出 JSON：{{"order_quantity": <int>, "reasoning": "..."}}，且 order_quantity>=0。
- 你必须使用 agent_id={agent_id} 作为决策者智能体。

请输出一个可直接保存并执行的 Simulation（JSON）。
""".strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("BASE_URL", "http://127.0.0.1:8001"))
    ap.add_argument("--username", default=os.environ.get("SIM_USER", f"u_{uuid.uuid4().hex[:8]}"))
    ap.add_argument("--password", default=os.environ.get("SIM_PASS", "pass1234"))
    ap.add_argument("--provider", default=os.environ.get("PROVIDER", "deepseek"))
    ap.add_argument("--model", default=os.environ.get("MODEL", "deepseek-chat"))
    ap.add_argument("--agent-base-url", default=os.environ.get("AGENT_BASE_URL"))
    ap.add_argument("--api-key", default=os.environ.get("API_KEY"))
    ap.add_argument("--save-artifacts", action="store_true")
    ap.add_argument("--include-refs", type=int, default=1, help="1=上传参考文献PDF给生成接口，0=不上传")
    args = ap.parse_args()

    auth = register_and_login(args.base_url, args.username, args.password)
    template_agent = ensure_template_agent(auth, args.provider, args.model, args.agent_base_url, args.api_key)
    agent_id = template_agent["id"]

    # 上传文件：阅读报告 + 关键参考文献（先少量，避免过长）
    file_names: List[str] = []
    report = Path("行为库存管理/Reading_Report_BOM_Evolution_CuiEtAl_2025.pdf")
    if not report.exists():
        raise RuntimeError(f"Missing report: {report}")

    file_names.append(upload_temp_file(auth, report))

    if args.include_refs:
        refs = [
            Path("行为库存管理/参考文献/Cachon_schweitzer_ms.pdf"),
            Path("行为库存管理/参考文献/bostian_holt_smith_2007.pdf"),
            Path("行为库存管理/参考文献/Ren-OverconfidenceNewsvendorOrders-2013.pdf"),
            Path("行为库存管理/参考文献/simon-herbert_a-behavioral-model-of-rational-choice-1955-feb.pdf"),
            Path("行为库存管理/参考文献/Kahneman-Tversky-Prospect-theory-1979.pdf"),
        ]
        for p in refs:
            if p.exists():
                file_names.append(upload_temp_file(auth, p))

    prompt = build_prompt(agent_id)
    sim = generate_simulation(auth, prompt, file_names=file_names)

    saved = save_simulation(auth, sim)
    run = execute_simulation(auth, saved)
    report = quality_report(saved, run)

    print("\n=== QUALITY REPORT ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.save_artifacts:
        out_dir = Path("artifacts/results/behavioral_inventory")
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        (out_dir / f"pull_to_center_sim_{ts}.json").write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / f"pull_to_center_run_{ts}.json").write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / f"pull_to_center_report_{ts}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Artifacts saved to {out_dir}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[FAILED] {e}")
        sys.exit(1)
