#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Paper-driven redesign + rerun for Behavioral Inventory (Part 3) suite.

Goal
- Use your "creative AI" (a duplicate of ai1 if available) to read referenced papers
  (via extracted snippets) and redesign each simulation so that:
  - treatments / tasks / metrics align better with the paper's experimental design
  - results are measurable in exported artifacts (state['history'] and state['summary'])
- Save redesigned simulations into a new suite folder under artifacts/results/<target-suite>/
- Rerun all redesigned simulations using scripts/analysis/run_part3_suite_and_report.py
- (Optional) run paper-alignment analysis afterwards (use a separate script).

Run with backend venv (needs pypdf):
  backend/.venv/bin/python scripts/analysis/redesign_and_rerun_part3_suite_from_papers.py \
    --base-url http://127.0.0.1:8001 --username <u> --password <p>

Notes
- This script uses /api/chat to have the creative agent produce a full Simulation JSON.
- It enforces a strict safety/runnability validator on code steps (no def/lambda/eval/exec/compile).
- It forces use_rag=False on all agent/dialogue steps in the redesigned simulations.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
BOM_DIR = ROOT / "行为库存管理"
REF_DIR = BOM_DIR / "参考文献"

SOURCE_SUITE_NAME_DEFAULT = "behavioral_inventory_part3_suite"
TARGET_SUITE_NAME_DEFAULT = "behavioral_inventory_part3_suite_paper_redesign"


KEYWORDS = [
    "result",
    "results",
    "conclusion",
    "conclusions",
    "discussion",
    "experiment",
    "experiments",
    "treatment",
    "study",
    "table",
    "figure",
    "hypothesis",
    "effect",
]


SUITE_EXPERIMENTS: List[Dict[str, Any]] = [
    {
        "slug": "confirmation_bias_advertising",
        "title": "Confirmation Bias in Advertising",
        "refs": [
            "Production   Oper Manag - 2020 - Bagchi - Strategic Implications of Confirmation Bias‐Inducing Advertising.pdf",
        ],
    },
    {
        "slug": "forecasting_service_level_anchor",
        "title": "Forecasting vs Service Level Anchor",
        "refs": [
            "A_hidden_anchor_The_influence_of_service_levels_on.pdf",
            "Tong_Feiler_-_Behavioral_Model_of_Forecasting_-_Man_Sci_-_2017.pdf",
        ],
    },
    {
        "slug": "herding_in_queues",
        "title": "Herding in Queues",
        "refs": [
            "herding_in_queues.pdf",
            "InfoDisclosure-Herding.pdf",
        ],
    },
    {
        "slug": "human_algorithm_naw",
        "title": "Human-Algorithm Collaboration (NAW)",
        "refs": [
            "Human-Algorithm Collaboration with Private Information_14b8d3ac-7e23-4a41-8877-8de26238431d.pdf",
        ],
    },
    {
        "slug": "newsvendor_pull_to_center",
        "title": "Newsvendor Pull-to-Center + Debias",
        "refs": [
            "Cachon_schweitzer_ms.pdf",
            "bostian_holt_smith_2007.pdf",
            "Ren-OverconfidenceNewsvendorOrders-2013.pdf",
        ],
    },
    {
        "slug": "overconfidence_calibration",
        "title": "Overconfidence & Calibration",
        "refs": [
            "Ren-OverconfidenceNewsvendorOrders-2013.pdf",
        ],
    },
    {
        "slug": "prospect_theory_pricing_regret",
        "title": "Pricing Framing (Prospect/Regret)",
        "refs": [
            "Kahneman-Tversky-Prospect-theory-1979.pdf",
            "Advance_Selling_When_Consumers_Regret.pdf",
            "Nasiry-DynamicPricingLossAverse-2011.pdf",
        ],
    },
    {
        "slug": "response_time_bargaining",
        "title": "Response Time Information in Bargaining",
        "refs": [
            "The_Value_of_Response_Time_Information_in_Supply_C.pdf",
        ],
    },
    {
        "slug": "trust_in_info_sharing",
        "title": "Trust in Forecast Information Sharing",
        "refs": [
            "mnsc.1110.1334.1.pdf",
            "07_23_Communication Media.pdf",
        ],
    },
]


@dataclass
class Auth:
    base_url: str
    token: str


def _post_json(s: requests.Session, url: str, payload: Any, timeout: float = 120.0) -> Any:
    r = s.post(url, json=payload, timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"POST {url} failed: {r.status_code} {r.text}")
    return r.json()


def _put_json(s: requests.Session, url: str, payload: Any, timeout: float = 120.0) -> Any:
    r = s.put(url, json=payload, timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"PUT {url} failed: {r.status_code} {r.text}")
    return r.json()


def _get_json(s: requests.Session, url: str, timeout: float = 60.0) -> Any:
    r = s.get(url, timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"GET {url} failed: {r.status_code} {r.text}")
    return r.json()


def _login(base_url: str, username: str, password: str) -> Auth:
    s = requests.Session()
    r = s.post(
        f"{base_url}/api/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Login failed: {r.status_code} {r.text}")
    return Auth(base_url=base_url, token=r.json()["access_token"])


def _register_if_needed(base_url: str, username: str, password: str) -> None:
    s = requests.Session()
    try:
        _post_json(s, f"{base_url}/api/register", {"username": username, "password": password}, timeout=30)
    except Exception:
        # ok if already exists
        return


def _extract_pdf_evidence(pdf_path: Path, keywords: List[str], max_pages: int = 80, max_snippets: int = 8) -> List[Dict[str, Any]]:
    reader = PdfReader(str(pdf_path))
    snippets: List[Dict[str, Any]] = []
    for i, page in enumerate(reader.pages[:max_pages]):
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            continue
        if not text:
            continue
        low = text.lower()
        if any(k in low for k in keywords):
            compact = re.sub(r"\s+", " ", text)
            compact = compact[:2000]
            snippets.append({"page": i + 1, "text": compact})
            if len(snippets) >= max_snippets:
                break
    if not snippets:
        try:
            t0 = (reader.pages[0].extract_text() or "").strip()
        except Exception:
            t0 = ""
        compact = re.sub(r"\s+", " ", t0)[:2000]
        snippets.append({"page": 1, "text": compact or "(PDF 文本抽取失败：可能为扫描版/特殊字体编码)"})
    return snippets


def _summarize_sim_for_prompt(sim: Dict[str, Any], max_steps: int = 24) -> Dict[str, Any]:
    steps = sim.get("steps") or []
    flat = []

    def walk(xs: List[Dict[str, Any]]):
        for st in xs:
            flat.append({"id": st.get("id"), "type": st.get("type"), "output_var": st.get("output_var")})
            inner = st.get("inner_steps")
            if isinstance(inner, list) and inner:
                walk(inner)

    walk(steps)
    vars_list = sim.get("variables") or []
    var_keys = [v.get("key") for v in vars_list if isinstance(v, dict) and v.get("key")]
    return {
        "name": sim.get("name"),
        "description": (sim.get("description") or "")[:400],
        "variables_keys": var_keys[:60],
        "steps_outline": flat[:max_steps],
    }


def _extract_json(text: Any) -> Any:
    if not isinstance(text, str):
        return text
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    try:
        return json.loads(text)
    except Exception:
        return text


def _walk_steps(steps: List[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for st in steps:
        yield st
        inner = st.get("inner_steps")
        if isinstance(inner, list) and inner:
            yield from _walk_steps(inner)


def _validate_simulation_syntax_and_safety(sim: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    for st in _walk_steps(sim.get("steps") or []):
        if st.get("type") != "code":
            continue
        code = st.get("code_snippet")
        if not isinstance(code, str) or not code.strip():
            continue
        low = code.lower()
        banned = ["eval(", "compile(", "exec(", "__code__", "co_consts", "marshal"]
        for b in banned:
            if b in low:
                issues.append(f"banned_token:{b}")
        if "def " in low or "lambda " in low:
            issues.append("function_definition_in_code")
        try:
            compile(code, f"<{st.get('id','code')}>", "exec")
        except SyntaxError as e:
            issues.append(f"syntax_error:{e.msg}")
    return sorted(list(set(issues)))


def _normalize_simulation(sim: Dict[str, Any], force_disable_memory: bool = True) -> Dict[str, Any]:
    sim = dict(sim)
    # variables: ensure list[dict] with string values
    vars_out: List[Dict[str, Any]] = []
    for v in (sim.get("variables") or []):
        if not isinstance(v, dict):
            continue
        key = v.get("key")
        if not isinstance(key, str) or not key.strip():
            continue
        val = v.get("value", "")
        if isinstance(val, (dict, list)):
            val = json.dumps(val, ensure_ascii=False)
        elif isinstance(val, (int, float, bool)) or val is None:
            val = str(val)
        elif not isinstance(val, str):
            val = str(val)
        desc = v.get("description")
        if desc is not None and not isinstance(desc, str):
            desc = str(desc)
        vars_out.append({"key": key, "value": val, "description": desc or ""})
    sim["variables"] = vars_out

    # steps: ensure ids; force use_rag=False for agent/dialogue to avoid contamination
    steps = sim.get("steps") or []
    if not isinstance(steps, list):
        steps = []
    for st in _walk_steps(steps):
        if not isinstance(st, dict):
            continue
        if not st.get("id"):
            st["id"] = f"step-{uuid.uuid4().hex[:8]}"
        if force_disable_memory and st.get("type") in {"agent", "dialogue"}:
            st["use_rag"] = False
        # avoid relying on file attachments for runner agent
        if "files" in st and isinstance(st.get("files"), list):
            st["files"] = []
    sim["steps"] = steps

    if not isinstance(sim.get("name"), str) or not sim.get("name"):
        sim["name"] = "Paper Redesign Simulation"
    if not isinstance(sim.get("description"), str):
        sim["description"] = str(sim.get("description") or "")

    return sim


def _ensure_creative_agent(s: requests.Session, provider: str, model: str, llm_base_url: Optional[str], api_key: Optional[str]) -> Dict[str, Any]:
    agents = _get_json(s, f"{auth.base_url}/api/agents")
    if not isinstance(agents, list):
        agents = []

    ai1 = None
    for a in agents:
        if isinstance(a, dict) and isinstance(a.get("name"), str) and "ai1" in a.get("name").lower():
            ai1 = a
            break

    base = ai1 or (agents[0] if agents else None)
    if base is None:
        payload: Dict[str, Any] = {
            "name": "Creative Agent (Part3 Redesign)",
            "provider": provider,
            "model": model,
            "base_url": llm_base_url,
            "api_key": api_key,
            "persona": "你是研究设计/实验方法专家。你必须输出严格 JSON，不要输出多余文本。",
            "long_term_memory": [],
        }
        return _post_json(s, f"{auth.base_url}/api/agents", payload)

    dup = _post_json(s, f"{auth.base_url}/api/agents/{base['id']}/duplicate", {})
    new_id = dup.get("id")
    if new_id:
        _put_json(s, f"{auth.base_url}/api/agents/{new_id}", {"name": f"ai1复制体-论文精读重设-{time.strftime('%Y%m%d_%H%M%S')}"})
        # clear memory and history
        try:
            _put_json(s, f"{auth.base_url}/api/agents/{new_id}/memory", [])
        except Exception:
            pass
        try:
            s.delete(f"{auth.base_url}/api/agents/{new_id}/history", timeout=30)
        except Exception:
            pass
    return _get_json(s, f"{auth.base_url}/api/agents/{new_id}") if new_id else dup


def _chat_json(s: requests.Session, agent_id: str, user_prompt: str, temperature: float = 0.2, max_tokens: int = 6000) -> Any:
    payload = {
        "agent_id": agent_id,
        "messages": [{"role": "user", "content": user_prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    return _post_json(s, f"{auth.base_url}/api/chat", payload, timeout=1200)


def _save_simulation(s: requests.Session, sim: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "name": sim.get("name") or "Paper Redesign Simulation",
        "description": sim.get("description") or "",
        "steps": sim.get("steps") or [],
        "variables": sim.get("variables") or [],
    }
    return _post_json(s, f"{auth.base_url}/api/simulations", payload, timeout=60)


def _latest_sim_path_for_slug(results_root: Path, slug: str) -> Path:
    d = results_root / slug
    sims = sorted(d.glob("sim_*.json"))
    if not sims:
        raise FileNotFoundError(f"No sim_*.json under {d}")
    return sims[-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("AISIM_BASE_URL", "http://127.0.0.1:8001"))
    ap.add_argument("--username", default=os.environ.get("AISIM_USER", f"redesign_{uuid.uuid4().hex[:8]}"))
    ap.add_argument("--password", default=os.environ.get("AISIM_PASS", "pass1234"))

    ap.add_argument("--provider", default=os.environ.get("AISIM_PROVIDER", "deepseek"))
    ap.add_argument("--model", default=os.environ.get("AISIM_MODEL", "deepseek-chat"))
    ap.add_argument("--llm-base-url", default=os.environ.get("AISIM_LLM_BASE_URL"))
    ap.add_argument("--api-key", default=os.environ.get("AISIM_LLM_API_KEY"))

    ap.add_argument("--source-suite-name", default=SOURCE_SUITE_NAME_DEFAULT)
    ap.add_argument("--target-suite-name", default=TARGET_SUITE_NAME_DEFAULT)
    ap.add_argument("--max-attempts", type=int, default=2)
    ap.add_argument("--only", type=str, default="")

    ap.add_argument("--smoke-rounds", type=int, default=8)
    ap.add_argument("--max-steps", type=int, default=3000)
    ap.add_argument("--skip-rerun", action="store_true")

    args = ap.parse_args()

    global auth
    _register_if_needed(args.base_url, args.username, args.password)
    auth = _login(args.base_url, args.username, args.password)

    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth.token}"})

    creative = _ensure_creative_agent(s, args.provider, args.model, args.llm_base_url, args.api_key)
    creative_id = creative.get("id")
    if not creative_id:
        raise RuntimeError("Failed to create/duplicate creative agent")

    source_root = ROOT / "artifacts" / "results" / args.source_suite_name
    target_root = ROOT / "artifacts" / "results" / args.target_suite_name
    target_root.mkdir(parents=True, exist_ok=True)

    only = {x.strip() for x in args.only.split(",") if x.strip()} if args.only.strip() else None

    ts = time.strftime("%Y%m%d_%H%M%S")
    index: Dict[str, Any] = {
        "timestamp": ts,
        "source_suite": args.source_suite_name,
        "target_suite": args.target_suite_name,
        "creative_agent_id": creative_id,
        "experiments": [],
    }

    for exp in SUITE_EXPERIMENTS:
        slug = exp["slug"]
        if only and slug not in only:
            continue

        item: Dict[str, Any] = {"slug": slug, "title": exp.get("title"), "status": "started", "refs": exp.get("refs")}
        try:
            current_sim_path = _latest_sim_path_for_slug(source_root, slug)
            current_sim = json.loads(current_sim_path.read_text("utf-8"))
            item["source_sim_path"] = str(current_sim_path.relative_to(ROOT))

            # Evidence from refs
            evidence_blocks = []
            for fn in exp.get("refs") or []:
                p = REF_DIR / fn
                if not p.exists():
                    continue
                snippets = _extract_pdf_evidence(p, KEYWORDS)
                evidence_blocks.append({"file": fn, "snippets": snippets})

            sim_summary = _summarize_sim_for_prompt(current_sim)

            common_rules = """
HARD REQUIREMENTS (must follow):
- Output STRICT JSON only.
- Provide a Simulation JSON with: name, description, variables(list), steps(list).
- Use only Python standard library in code steps. Do NOT use scipy/numpy/pandas.
- Record all trial-level results into state['history'] (a list of dicts).
- At the end, compute state['summary'] with condition-level aggregates.
- Keep it runnable with the platform engine: steps executed one-by-one; loops via inner_steps + loop.

ROBUSTNESS / SAFETY:
- world_state/state MUST remain JSON-serializable at all times.
- NEVER store functions/modules/class instances in state.
- Do NOT use eval/exec/compile in any code step.
- Do NOT define helper functions (no 'def' or 'lambda') inside code steps.
- Any list/dict in variables MUST be valid JSON (double quotes).
- All agent steps must request STRICT JSON and parse robustly.
- Do NOT rely on file attachments; all needed task description must be in prompt/state.
""".strip()

            user_prompt = (
                f"You are redesigning an experiment simulation to better match the referenced paper.\n\n"
                f"EXPERIMENT SLUG: {slug}\nTITLE: {exp.get('title')}\n\n"
                f"{common_rules}\n\n"
                f"PAPER EVIDENCE (snippets with page numbers):\n{json.dumps(evidence_blocks, ensure_ascii=False, indent=2)}\n\n"
                f"CURRENT SIM (summary only):\n{json.dumps(sim_summary, ensure_ascii=False, indent=2)}\n\n"
                "TASK:\n"
                "1) Infer the paper's actual experimental design (treatments, task interface, incentive, sample size, key outcomes).\n"
                "2) Redesign the simulation so that our exported history/summary can test the paper's directional conclusions.\n"
                "3) Ensure the agent prompts are unambiguous and numeric outputs are well-defined.\n\n"
                "OUTPUT JSON SCHEMA (must follow):\n"
                "{\n"
                "  \"paper_design\": {\"treatments\":..., \"task\":..., \"outcomes\":..., \"expected_direction\":...},\n"
                "  \"simulation\": {\"name\":..., \"description\":..., \"variables\":[...], \"steps\":[...]},\n"
                "  \"verification\": {\"how_to_judge\":..., \"primary_metrics\":[...]}\n"
                "}\n"
            )

            redesigned: Optional[Dict[str, Any]] = None
            last_err: Optional[str] = None

            for attempt in range(1, max(1, args.max_attempts) + 1):
                prompt_attempt = user_prompt
                if attempt > 1 and last_err:
                    prompt_attempt += f"\n\nPREVIOUS ATTEMPT FAILED: {last_err}\nPlease output a corrected JSON only."

                resp = _chat_json(s, creative_id, prompt_attempt)
                content = resp.get("content") if isinstance(resp, dict) else None
                parsed = _extract_json(content)
                if isinstance(parsed, dict) and isinstance(parsed.get("simulation"), dict):
                    redesigned = parsed
                elif isinstance(parsed, dict) and isinstance(parsed.get("steps"), list):
                    redesigned = {"paper_design": {}, "simulation": parsed, "verification": {}}
                else:
                    last_err = "could_not_parse_json"
                    continue

                sim_obj = _normalize_simulation(redesigned.get("simulation") or {})
                issues = _validate_simulation_syntax_and_safety(sim_obj)
                if issues:
                    last_err = "static_validation_failed: " + ", ".join(issues[:8])
                    redesigned = None
                    continue

                # also enforce that agent/dialogue are memory-off
                for st in _walk_steps(sim_obj.get("steps") or []):
                    if st.get("type") in {"agent", "dialogue"}:
                        st["use_rag"] = False
                redesigned["simulation"] = sim_obj
                break

            if redesigned is None:
                raise RuntimeError(last_err or "redesign_failed")

            sim_obj = redesigned["simulation"]
            # name normalization
            if "[PaperRedesign]" not in (sim_obj.get("name") or ""):
                sim_obj["name"] = f"{sim_obj.get('name') or exp.get('title')} [PaperRedesign]"

            saved = _save_simulation(s, sim_obj)
            item["simulation_id"] = saved.get("id")
            item["simulation_name"] = saved.get("name")
            item["status"] = "saved"

            # persist artifacts
            out_dir = target_root / slug
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"sim_{ts}.json").write_text(json.dumps(sim_obj, ensure_ascii=False, indent=2), encoding="utf-8")
            meta = {
                "slug": slug,
                "timestamp": ts,
                "saved_simulation_id": saved.get("id"),
                "paper_design": redesigned.get("paper_design"),
                "verification": redesigned.get("verification"),
                "evidence_files": exp.get("refs"),
            }
            (out_dir / f"redesign_meta_{ts}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

            # clear creative agent memory/history to avoid cross-contamination
            try:
                _put_json(s, f"{auth.base_url}/api/agents/{creative_id}/memory", [])
            except Exception:
                pass
            try:
                s.delete(f"{auth.base_url}/api/agents/{creative_id}/history", timeout=30)
            except Exception:
                pass

        except Exception as e:
            item["status"] = "failed"
            item["error"] = str(e)

        index["experiments"].append(item)

    # write index
    (target_root / f"index_{ts}.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = sum(1 for x in index["experiments"] if x.get("status") == "saved")
    print(f"Redesign saved. experiments={len(index['experiments'])} ok={ok}")

    if args.skip_rerun:
        print("skip_rerun=true")
        return 0

    # rerun via existing runner (parameterized)
    cmd = [
        str(ROOT / "scripts" / "analysis" / "run_part3_suite_and_report.py"),
        "--base-url",
        args.base_url,
        "--provider",
        args.provider,
        "--model",
        args.model,
        "--username",
        args.username,
        "--password",
        args.password,
        "--smoke-rounds",
        str(args.smoke_rounds),
        "--max-steps",
        str(args.max_steps),
        "--suite-name",
        args.target_suite_name,
        "--suite-root",
        str(target_root),
        "--force-use-rag",
        "false",
    ]
    if args.llm_base_url:
        cmd += ["--llm-base-url", args.llm_base_url]
    if args.api_key:
        cmd += ["--api-key", args.api_key]

    print("Running suite runner:")
    print(" ".join(cmd))
    subprocess.run([sys.executable] + cmd, check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
