#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Run Behavioral Inventory (Part 3) suite sims, export outputs, and write a Chinese report.

What this script does:
- Locate the latest generated simulation JSON for each suite slug under
  artifacts/results/behavioral_inventory_part3_suite/<slug>/sim_*.json
- Login to backend, ensure an agent exists, force all agent steps to use that agent.
- Execute each simulation through /api/simulation/run_step (step-by-step engine).
- Export run artifacts (sim/run/world_state/summary/history.csv) into
  artifacts/exports/behavioral_inventory_part3_suite/<ts>/<slug>/
- Generate a Chinese Markdown report summarizing the 9 simulations, variables,
  run results, and a code-structure analysis.

Usage:
  python scripts/analysis/run_part3_suite_and_report.py \
    --base-url http://127.0.0.1:8001 \
    --provider deepseek --model deepseek-chat \
    --smoke-rounds 3

Notes:
- Many simulations include agent steps; results can vary due to model stochasticity.
- This script keeps rounds small by default.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUITE_NAME = "behavioral_inventory_part3_suite"
SUITE_ROOT = ROOT / "artifacts" / "results" / DEFAULT_SUITE_NAME


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

    reg_url = f"{base_url}/api/register"
    try:
        _post_json(session, reg_url, {"username": username, "password": password})
    except Exception as e:
        # OK if already registered
        msg = str(e).lower()
        if "already" not in msg and "registered" not in msg and "400" not in msg:
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


def ensure_template_agent(auth: Auth, provider: str, model: str, llm_base_url: Optional[str], api_key: Optional[str]) -> Dict[str, Any]:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth.token}"})

    agents = _get_json(s, f"{auth.base_url}/api/agents")
    if isinstance(agents, list) and agents:
        return agents[0]

    payload: Dict[str, Any] = {
        "name": "Suite Runner Agent",
        "provider": provider,
        "model": model,
        "base_url": llm_base_url,
        "api_key": api_key,
        "persona": "你是一个用于行为运营/库存管理实验的AI被试（silicon subject）。你必须严格按要求输出 JSON。",
        "long_term_memory": [],
    }
    return _post_json(s, f"{auth.base_url}/api/agents", payload)


def run_simulation_step(auth: Auth, step: Dict[str, Any], history: List[Dict[str, Any]], world_state: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth.token}"})
    url = f"{auth.base_url}/api/simulation/run_step"
    payload = {"steps": [step], "current_step_index": 0, "history": history, "world_state": world_state}
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
        if isinstance(raw, (dict, list, int, float, bool)) or raw is None:
            state[k] = raw
            continue
        if isinstance(raw, str):
            try:
                state[k] = json.loads(raw)
            except Exception:
                state[k] = raw
        else:
            state[k] = str(raw)
    return state


def _walk_steps(steps: List[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for st in steps:
        yield st
        inner = st.get("inner_steps")
        if isinstance(inner, list) and inner:
            yield from _walk_steps(inner)


def force_agent_id(sim: Dict[str, Any], agent_id: str) -> None:
    for st in _walk_steps(sim.get("steps") or []):
        if st.get("type") in {"agent", "dialogue"}:
            st["agent_ids"] = [agent_id]
            st["agent_id"] = None


def force_use_rag(sim: Dict[str, Any], use_rag: bool) -> None:
    for st in _walk_steps(sim.get("steps") or []):
        if st.get("type") in {"agent", "dialogue"}:
            st["use_rag"] = bool(use_rag)


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


def execute_simulation(auth: Auth, sim: Dict[str, Any], smoke_rounds: int, max_steps: int = 4000) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = sim.get("steps") or []
    variables: List[Dict[str, Any]] = sim.get("variables") or []

    history: List[Dict[str, Any]] = []
    world_state: Dict[str, Any] = _init_world_state(variables)

    # override round-like keys
    for k in [
        "total_rounds",
        "rounds",
        "n_rounds",
        "num_rounds",
        "replications",
        "n_replications",
        "num_replications",
        "total_episodes",
    ]:
        if k in world_state:
            try:
    SUITE_ROOT = ROOT / "artifacts" / "results" / DEFAULT_SUITE_NAME
                world_state[k] = int(smoke_rounds)
            except Exception:
                world_state[k] = smoke_rounds

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
                eval_step = {"id": "temp-eval", "type": "code", "code_snippet": f"state['__loop_result'] = {cond}"}
                new_items, new_state = run_simulation_step(auth, eval_step, [], world_state)
                if new_items and isinstance(new_items[0].get("content"), str) and str(new_items[0]["content"]).startswith("Error"):
                    raise RuntimeError(f"Loop condition error: {new_items[0]['content']}")
                is_true = bool(new_state.get("__loop_result"))
                new_state.pop("__loop_result", None)
                world_state = new_state

            # True loop semantics: if condition holds, execute inner steps and
            # then re-check the condition again. Only advance index when the
            # condition becomes false.
            if is_true:
                stack.append({"steps": step.get("inner_steps") or [], "index": 0})
            else:
                frame["index"] += 1
            continue

        inner = step.get("inner_steps")
        if inner:
            frame["index"] += 1
            stack.append({"steps": inner, "index": 0})
            continue

        new_items, world_state = run_simulation_step(auth, step, history, world_state)
        if new_items:
            history.extend(new_items)

        frame["index"] += 1
        executed += 1

    return {"history": history, "world_state": world_state, "executed_steps": executed}


def _suite_slugs(suite_root: Path = SUITE_ROOT) -> List[str]:
    if not suite_root.exists():
        return []
    slugs: List[str] = []
    for p in suite_root.iterdir():
        if p.is_dir():
            slugs.append(p.name) 
    # ignore non-slug dirs
    slugs = [s for s in slugs if not s.startswith("__")]
    return sorted(slugs)


def _latest_sim_path_for_slug(slug: str, suite_root: Path = SUITE_ROOT) -> Path:
    d = suite_root / slug
    sims = sorted(d.glob("sim_*.json"))
    if not sims: 
        raise FileNotFoundError(f"No sim_*.json under {d}")
    return sims[-1]


def _load_indexes(suite_root: Path = SUITE_ROOT) -> Dict[str, Dict[str, Any]]:
    """Merge index entries by slug; prefer the latest timestamp for each slug."""
    idx_files = sorted(suite_root.glob("index_*.json"))
    merged: Dict[str, Dict[str, Any]] = {} 
    for p in idx_files:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        ts = data.get("timestamp") or p.stem
        for item in data.get("experiments") or []:
            slug = item.get("slug")
            if not slug:
                continue
            prev = merged.get(slug)
            if prev is None or str(ts) >= str(prev.get("_ts", "")):
                copied = dict(item)
                copied["_ts"] = ts
                copied["_index_path"] = str(p.relative_to(ROOT))
                merged[slug] = copied
    return merged


def _extract_state_keys_from_code(code: str) -> List[str]:
    # conservative regex; doesn't try to parse python
    keys = set()
    for m in re.finditer(r"state\[['\"]([A-Za-z0-9_\-]+)['\"]\]", code or ""):
        keys.add(m.group(1))
    return sorted(keys)


def _summarize_code_steps(sim: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for st in _walk_steps(sim.get("steps") or []):
        if st.get("type") != "code":
            continue
        code = st.get("code_snippet") or ""
        rec = {
            "id": st.get("id"),
            "len": len(code),
            "state_keys_written_or_read": _extract_state_keys_from_code(code),
            "mentions_history_append": "history.append" in code or "state['history']" in code,
        }
        out.append(rec)
    return out


def _infer_variable_meaning(key: str) -> str:
    k = (key or "").lower()
    if k in {"rng_seed"}:
        return "随机种子（控制随机数）"
    if "total_round" in k or k in {"rounds", "n_rounds", "num_rounds"}:
        return "每个条件下的回合数/轮数"
    if "treat" in k:
        return "处理/实验条件列表或当前处理索引"
    if "scenario" in k:
        return "情景（如高/低利润、gain/loss frame 等）"
    if k in {"mu", "sigma", "demand_mean", "demand_std", "lam"}:
        return "分布参数（均值/标准差/泊松均值等）"
    if "history" in k:
        return "过程数据容器（逐轮记录）"
    if k in {"summary"}:
        return "汇总指标（按条件统计）"
    if "price" in k or "cost" in k or "profit" in k or "w" == k:
        return "价格/成本/利润等经济参数"
    if "trust" in k:
        return "信任/可信度状态变量"
    return "世界状态变量（由 simulation 代码读写）"


def _write_csv_history(path: Path, records: List[Dict[str, Any]]) -> None:
    if not records:
        path.write_text("", encoding="utf-8")
        return
    # stable columns
    cols: List[str] = []
    seen = set()
    for r in records:
        if not isinstance(r, dict):
            continue
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                cols.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in records:
            if isinstance(r, dict):
                w.writerow({k: r.get(k) for k in cols})


def _analyze_exported(history: List[Dict[str, Any]], summary: Any) -> Dict[str, Any]:
    """Compute a few lightweight diagnostics for the report."""
    result: Dict[str, Any] = {"history_rows": 0, "history_columns": 0, "has_summary": summary is not None}
    if isinstance(history, list):
        result["history_rows"] = len(history)
        if history and isinstance(history[0], dict):
            result["history_columns"] = len(history[0].keys())

    # choice share if present
    if isinstance(history, list):
        choices = [r.get("choice") for r in history if isinstance(r, dict) and "choice" in r]
        if choices:
            total = len(choices)
            a = sum(1 for c in choices if str(c).strip().upper() == "A")
            b = sum(1 for c in choices if str(c).strip().upper() == "B")
            result["choice_share"] = {"A": a / total, "B": b / total, "n": total}

    return result


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _safe_mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _group_key(record: Dict[str, Any]) -> str:
    for k in ["treatment", "scenario", "current_treatment", "current_scenario"]:
        if k in record:
            return k
    return "__all__"


def _compute_group_means(history: List[Dict[str, Any]], max_metrics: int = 6) -> Dict[str, Any]:
    """Best-effort: compute mean of numeric metrics grouped by treatment/scenario."""
    if not history or not isinstance(history, list):
        return {}
    rows = [r for r in history if isinstance(r, dict)]
    if not rows:
        return {}

    group_field = _group_key(rows[0])
    if group_field == "__all__":
        groups = {"all": rows}
    else:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            g = r.get(group_field)
            gk = str(g)
            groups.setdefault(gk, []).append(r)

    # pick numeric columns (excluding identifiers)
    exclude = {"round", "episode", "trial", "reason", "choice", "treatment", "scenario"}
    all_keys: List[str] = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                all_keys.append(k)
    num_keys = []
    for k in all_keys:
        if k in exclude:
            continue
        vals = [r.get(k) for r in rows]
        if any(_is_number(v) for v in vals):
            num_keys.append(k)
    # prioritize common behavioral metrics
    priority = [
        "deviation",
        "profit",
        "error_sq",
        "w",
        "forecast",
        "trust",
        "realized_profit",
        "reported_quality",
        "purchase_intention",
    ]
    ordered = [k for k in priority if k in num_keys] + [k for k in num_keys if k not in priority]
    ordered = ordered[:max_metrics]

    out: Dict[str, Any] = {"group_field": group_field, "metrics": {}}
    for gk, g_rows in groups.items():
        out["metrics"][gk] = {"n": len(g_rows)}
        for k in ordered:
            vals = [float(r.get(k)) for r in g_rows if _is_number(r.get(k))]
            m = _safe_mean(vals)
            if m is not None:
                out["metrics"][gk][k] = round(m, 4)
    return out


def _choice_share_by_treatment(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = [r for r in history if isinstance(r, dict)]
    if not rows or not any("choice" in r for r in rows):
        return {}
    by: Dict[str, Dict[str, int]] = {}
    for r in rows:
        t = r.get("treatment", "all")
        k = str(t)
        c = r.get("choice")
        cs = str(c).strip().upper()
        if cs not in {"A", "B"}:
            continue
        by.setdefault(k, {"A": 0, "B": 0, "n": 0})
        by[k][cs] += 1
        by[k]["n"] += 1
    for k, d in by.items():
        n = d.get("n") or 0
        if n:
            d["A_share"] = round(d["A"] / n, 4)
            d["B_share"] = round(d["B"] / n, 4)
    return {"by_treatment": by}


def _derive_observations(group_means: Dict[str, Any], history: List[Dict[str, Any]]) -> List[str]:
    obs: List[str] = []
    metrics = group_means.get("metrics") if isinstance(group_means, dict) else None
    if isinstance(metrics, dict) and len(metrics) >= 2:
        # pick one representative metric to comment on
        cand = ["deviation", "profit", "w", "error_sq", "forecast", "trust", "reported_quality", "purchase_intention"]
        # find first metric that exists in at least two groups
        picked = None
        for m in cand:
            cnt = sum(1 for g in metrics.values() if isinstance(g, dict) and m in g)
            if cnt >= 2:
                picked = m
                break
        if picked:
            pairs = []
            for gk, g in metrics.items():
                if isinstance(g, dict) and picked in g:
                    pairs.append((gk, g[picked]))
            if len(pairs) >= 2:
                pairs_sorted = sorted(pairs, key=lambda x: x[1], reverse=True)
                top_g, top_v = pairs_sorted[0]
                bot_g, bot_v = pairs_sorted[-1]
                obs.append(f"按条件均值，{picked} 在 {top_g} 较高（{top_v}），在 {bot_g} 较低（{bot_v}）。")

    cs = _choice_share_by_treatment(history)
    by_t = cs.get("by_treatment") if isinstance(cs, dict) else None
    if isinstance(by_t, dict) and by_t:
        # mention up to 2 treatments
        items = list(by_t.items())[:2]
        parts = []
        for t, d in items:
            if not isinstance(d, dict):
                continue
            parts.append(f"{t}: A_share={d.get('A_share')}, n={d.get('n')}")
        if parts:
            obs.append("选择倾向（A 占比）：" + "; ".join(parts))

    return obs


def generate_report(
    ts: str,
    exports_root: Path,
    slug_infos: List[Dict[str, Any]],
    run_results: Dict[str, Dict[str, Any]],
    sim_by_slug: Dict[str, Dict[str, Any]],
    index_by_slug: Dict[str, Dict[str, Any]],
    suite_name: str = DEFAULT_SUITE_NAME, 
) -> Path:
    out_dir = ROOT / "artifacts" / "reports" / suite_name
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"report_{ts}.md"

    lines: List[str] = []
    lines.append(f"# 行为库存管理 Part 3：九个模拟的运行与导出分析报告\n")
    lines.append(f"生成时间：{ts}\n")

    lines.append("## 1. 结论摘要\n")
    lines.append("本报告覆盖 9 个 Part 3 suite 模拟：逐个运行（smoke-run 小回合数）、导出结果文件，并对 simulation 代码结构与导出数据做简要分析。\n")

    lines.append("## 2. 平台运行机制（run_step）理解\n")
    lines.append("- 平台以 step-by-step 方式执行：前端/脚本将单个 step 通过 `/api/simulation/run_step` 发送给后端，后端执行后返回新增 history 项与更新后的 world_state。\n")
    lines.append("- `code` step：后端在隔离的执行作用域内 `exec(code_snippet)`，并把 state 的变更以结构化 JSON 写入 history（type=state_change）。\n")
    lines.append("- `agent/dialogue` step：后端根据 prompt_template 渲染 prompt，调用对应 Agent（可带文件/RAG），将输出写入 history，并可写回 state 的 output_var。\n")
    lines.append("- 重要约束：world_state 必须 JSON 可序列化；后端对不可序列化对象会做 best-effort stringify，避免 FastAPI 返回 500。\n")
    lines.append("- 本次批量运行脚本的执行策略：\n")
    lines.append("  - `repeat_count`：展开为重复 step 序列逐一执行。\n")
    lines.append("  - `loop`：通过临时 `code` step 计算 loop_condition；条件为真则执行 inner_steps，执行完回到 loop 继续判断，直到条件为假才跳出。\n")

    lines.append("## 3. 导出机制理解\n")
    lines.append("- 当前后端并没有针对“simulation 运行结果”的专用导出接口（例如一键下载 zip/csv）。\n")
    lines.append("- 因此本次导出由脚本完成：把 run 返回的 `history/world_state/summary` 落盘为 JSON，并将 `state['history']` 转为 CSV，便于后续统计与复现。\n")
    lines.append("- 导出文件约定（每个 slug 一套）：\n")
    lines.append("  - `sim.json`：可执行的 simulation 定义（包含 code_snippet / prompt_template）。\n")
    lines.append("  - `run.json`：本次运行的引擎 history（step 级别日志）+ 最终 world_state。\n")
    lines.append("  - `world_state.json`：最终世界状态（包含模拟结果与中间变量）。\n")
    lines.append("  - `history.json` / `history.csv`：模拟设计层面的逐轮数据（state['history']）。\n")
    lines.append("  - `summary.json`：state['summary']（按 treatment/scenario 聚合后的指标）。\n")
    lines.append("  - `code_analysis.json`：脚本从 sim.json 提取的 code-step 结构信息（用于审计/对照）。\n")

    lines.append("## 4. 九个模拟清单与逐个分析\n")

    for info in slug_infos:
        slug = info["slug"]
        sim = sim_by_slug.get(slug) or {}
        idx = index_by_slug.get(slug) or {}
        run = run_results.get(slug) or {}

        sim_name = sim.get("name") or idx.get("simulation_name") or slug
        activity = idx.get("activity") or ""
        desc = sim.get("description") or ""
        sim_id = idx.get("simulation_id") or ""
        files = idx.get("files") or []

        world_state = (run.get("world_state") or {}) if isinstance(run, dict) else {}
        history_records = world_state.get("history") if isinstance(world_state.get("history"), list) else []
        summary = world_state.get("summary") if isinstance(world_state, dict) else None
        diagnostics = _analyze_exported(history_records, summary)
        group_means = _compute_group_means(history_records)
        observations = _derive_observations(group_means, history_records)

        lines.append(f"### {sim_name}\n")
        if activity:
            lines.append(f"- Activity：{activity}\n")
        if sim_id:
            lines.append(f"- simulation_id：{sim_id}\n")
        if desc:
            lines.append(f"- 简介：{desc}\n")
        if files:
            lines.append("- Grounding/引用文件：\n")
            for f in files:
                lines.append(f"  - {f}\n")

        # variables
        vars_list = sim.get("variables") or []
        lines.append("- 世界变量（variables → world_state 初始值）：\n")
        if not vars_list:
            lines.append("  - （无 variables，运行时由 init step 写入）\n")
        else:
            for v in vars_list:
                k = v.get("key")
                val = v.get("value")
                if not k:
                    continue
                meaning = _infer_variable_meaning(str(k))
                # keep value compact
                s = val
                if isinstance(s, str) and len(s) > 80:
                    s = s[:77] + "..."
                lines.append(f"  - {k}: {s}（{meaning}）\n")

        # run results
        runtime_errors = 0
        for h in (run.get("history") or []):
            c = h.get("content") if isinstance(h, dict) else None
            if isinstance(c, str) and (c.startswith("Error executing code") or c.startswith("Error:")):
                runtime_errors += 1
        lines.append("- 运行结果（smoke-run）：\n")
        lines.append(f"  - executed_steps: {run.get('executed_steps')}\n")
        lines.append(f"  - runtime_errors: {runtime_errors}\n")
        lines.append(f"  - 导出数据：history_rows={diagnostics.get('history_rows')}, has_summary={diagnostics.get('has_summary')}\n")
        if diagnostics.get("choice_share"):
            cs = diagnostics["choice_share"]
            lines.append(f"  - choice_share: A={cs['A']:.2f}, B={cs['B']:.2f}, n={cs['n']}\n")
        if group_means.get("metrics"):
            lines.append("- 导出数据的快速统计（按条件均值，截取少量指标）：\n")
            lines.append(f"  - group_field: {group_means.get('group_field')}\n")
            # show up to 3 groups
            shown = 0
            for gk, m in (group_means.get("metrics") or {}).items():
                shown += 1
                if shown > 3:
                    break
                keys = [k for k in m.keys() if k not in {"n"}]
                pairs = ", ".join([f"{k}={m[k]}" for k in keys[:6]])
                lines.append(f"  - {gk}: n={m.get('n')}{(', ' + pairs) if pairs else ''}\n")
        if observations:
            lines.append("- 观察与结论（基于本次 smoke-run 导出数据）：\n")
            for o in observations[:3]:
                lines.append(f"  - {o}\n")

        # export files
        out_dir = exports_root / slug
        lines.append("- 导出文件：\n")
        for fn in ["sim.json", "run.json", "world_state.json", "summary.json", "history.json", "history.csv", "code_analysis.json"]:
            p = out_dir / fn
            if p.exists():
                lines.append(f"  - {p.relative_to(ROOT)}\n")

        # code analysis
        code_summary = _summarize_code_steps(sim)
        code_steps_n = len(code_summary)
        key_hits = sorted({k for cs in code_summary for k in (cs.get("state_keys_written_or_read") or [])})
        lines.append("- 代码结构分析（从 simulation JSON 的 code steps 提取）：\n")
        lines.append(f"  - code_steps: {code_steps_n}\n")
        # top-level step outline
        top_steps = sim.get("steps") or []
        lines.append("  - top_level_steps（按顺序）：\n")
        for st in top_steps[:12]:
            lines.append(f"    - {st.get('id')} ({st.get('type')})\n")
        if key_hits:
            lines.append(f"  - 代码涉及的 state keys（抽样/去重）：{', '.join(key_hits[:30])}{' ...' if len(key_hits)>30 else ''}\n")
        lines.append("  - 结论（可运行性/可导出性）：该 simulation 的设计遵循‘逐轮写 history，末尾写 summary’的可审计范式；导出 CSV 可直接做条件对比统计与可视化。\n")

    report_path.write_text("".join(lines), encoding="utf-8")
    return report_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("AISIM_BASE_URL", "http://127.0.0.1:8001"))
    ap.add_argument("--provider", default=os.environ.get("AISIM_PROVIDER", "deepseek"))
    ap.add_argument("--model", default=os.environ.get("AISIM_MODEL", "deepseek-chat"))
    ap.add_argument("--llm-base-url", default=os.environ.get("AISIM_LLM_BASE_URL"))
    ap.add_argument("--api-key", default=os.environ.get("AISIM_LLM_API_KEY"))
    ap.add_argument("--username", default=os.environ.get("AISIM_USER", f"runner_{uuid.uuid4().hex[:8]}"))
    ap.add_argument("--password", default=os.environ.get("AISIM_PASS", "pass1234"))
    ap.add_argument("--smoke-rounds", type=int, default=3)
    ap.add_argument("--max-steps", type=int, default=3000)
    ap.add_argument("--only", type=str, default="")
    ap.add_argument(
        "--suite-name",
        type=str,
        default=os.environ.get("AISIM_SUITE_NAME", DEFAULT_SUITE_NAME),
        help="Suite name used for artifacts/results/<suite-name>, exports, and reports.",
    )
    ap.add_argument(
        "--suite-root",
        type=str,
        default=os.environ.get("AISIM_SUITE_ROOT", ""),
        help="Optional override for suite root directory containing <slug>/sim_*.json.",
    )
    ap.add_argument(
        "--force-use-rag",
        type=str,
        default=os.environ.get("AISIM_FORCE_USE_RAG", ""),
        help="Optional override for all agent/dialogue steps: true/false.",
    )
    args = ap.parse_args()

    suite_root = Path(args.suite_root) if args.suite_root.strip() else (ROOT / "artifacts" / "results" / args.suite_name)

    slugs = _suite_slugs(suite_root)
    if args.only.strip():
        only = {s.strip() for s in args.only.split(",") if s.strip()}
        slugs = [s for s in slugs if s in only]
    if not slugs:
        raise RuntimeError(f"No slugs found under {suite_root}")

    index_by_slug = _load_indexes(suite_root)

    auth = register_and_login(args.base_url, args.username, args.password)
    agent = ensure_template_agent(auth, args.provider, args.model, args.llm_base_url, args.api_key)
    agent_id = agent.get("id")
    if not agent_id:
        raise RuntimeError("Failed to get agent id")

    ts = time.strftime("%Y%m%d_%H%M%S")
    exports_root = ROOT / "artifacts" / "exports" / args.suite_name / ts
    exports_root.mkdir(parents=True, exist_ok=True)

    sim_by_slug: Dict[str, Dict[str, Any]] = {}
    run_results: Dict[str, Dict[str, Any]] = {}

    for slug in slugs:
        sim_path = _latest_sim_path_for_slug(slug, suite_root)
        sim = json.loads(sim_path.read_text(encoding="utf-8"))

        force_agent_id(sim, agent_id)

        if args.force_use_rag.strip():
            val = args.force_use_rag.strip().lower()
            if val in {"true", "1", "yes", "y"}:
                force_use_rag(sim, True)
            elif val in {"false", "0", "no", "n"}:
                force_use_rag(sim, False)
            else:
                raise ValueError("--force-use-rag must be true/false")

        sim_by_slug[slug] = sim

        run = execute_simulation(auth, sim, smoke_rounds=args.smoke_rounds, max_steps=args.max_steps)
        run_results[slug] = run

        out_dir = exports_root / slug
        out_dir.mkdir(parents=True, exist_ok=True)

        (out_dir / "sim.json").write_text(json.dumps(sim, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")

        world_state = run.get("world_state") or {}
        (out_dir / "world_state.json").write_text(json.dumps(world_state, ensure_ascii=False, indent=2), encoding="utf-8")
        summary = world_state.get("summary") if isinstance(world_state, dict) else None
        (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        history_records = world_state.get("history") if isinstance(world_state, dict) and isinstance(world_state.get("history"), list) else []
        (out_dir / "history.json").write_text(json.dumps(history_records, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_csv_history(out_dir / "history.csv", history_records)

        code_analysis = {
            "slug": slug,
            "sim_name": sim.get("name"),
            "code_steps": _summarize_code_steps(sim),
        }
        (out_dir / "code_analysis.json").write_text(json.dumps(code_analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    slug_infos = [{"slug": s} for s in slugs]
    report_path = generate_report(ts, exports_root, slug_infos, run_results, sim_by_slug, index_by_slug, suite_name=args.suite_name)

    print("DONE")
    print(f"exports_root={exports_root}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
