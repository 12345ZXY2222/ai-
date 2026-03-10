from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import json
import os
import re

from app.models.user import User
from app.api.endpoints import get_current_user
from app.core.adapter import ai_chat
from app.core.storage import load_data


router = APIRouter(prefix="/simulations", tags=["simulation-repair"])


class SimulationRepairRequest(BaseModel):
    simulation: Dict[str, Any]
    current_step_index: int = 0
    error_message: str
    history: List[Dict[str, Any]] = []
    world_state: Dict[str, Any] = {}


class SimulationRepairResponse(BaseModel):
    fixed_simulation: Dict[str, Any]
    explanation: str


def _extract_json_obj(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return {}
    return {}


def _resolve_user_chat_config(current_user: User) -> Dict[str, str]:
    agents_db = load_data("agents.json", {})
    if not isinstance(agents_db, dict):
        agents_db = {}

    candidates = [
        a for a in agents_db.values()
        if isinstance(a, dict) and a.get("user_id") == current_user.username
    ]
    for a in candidates:
        if a.get("provider") == "deepseek" and a.get("api_key"):
            return {
                "model": a.get("model") or os.environ.get("DEEPSEEK_DEFAULT_MODEL") or "deepseek-chat",
                "api_key": a.get("api_key") or "",
                "base_url": a.get("base_url") or os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com",
            }

    return {
        "model": os.environ.get("DEEPSEEK_DEFAULT_MODEL") or "deepseek-chat",
        "api_key": os.environ.get("DEEPSEEK_API_KEY") or "",
        "base_url": os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com",
    }


def _fallback_fix_simulation(sim: Dict[str, Any], current_step_index: int, error_message: str) -> tuple[Dict[str, Any], str]:
    """Deterministic fallback fixes for common runtime failures.

    This runs when LLM repair output is unavailable or invalid.
    """
    fixed = json.loads(json.dumps(sim, ensure_ascii=False)) if isinstance(sim, dict) else {}
    steps = fixed.get("steps") if isinstance(fixed.get("steps"), list) else []
    if not (0 <= current_step_index < len(steps)):
        return fixed, "未定位到当前步骤，保留原 simulation。"

    step = steps[current_step_index] if isinstance(steps[current_step_index], dict) else {}
    code = str(step.get("code_snippet") or "")
    err = (error_message or "").lower()

    # Case 1: JSON parsing failure from agent free-text output.
    if "expecting value" in err and "optimal_order_calc" in code:
        step["code_snippet"] = (
            "import json\n"
            "import re\n"
            "raw = state.get('optimal_order_calc', 50)\n"
            "if isinstance(raw, (int, float)):\n"
            "    opt = float(raw)\n"
            "else:\n"
            "    text = str(raw or '').strip()\n"
            "    try:\n"
            "        parsed = json.loads(text)\n"
            "        if isinstance(parsed, (int, float)):\n"
            "            opt = float(parsed)\n"
            "        elif isinstance(parsed, dict):\n"
            "            num = parsed.get('optimal_order')\n"
            "            opt = float(num) if isinstance(num, (int, float, str)) else 50.0\n"
            "        else:\n"
            "            opt = 50.0\n"
            "    except Exception:\n"
            "        nums = re.findall(r'[-+]?\\d*\\.?\\d+(?:[eE][-+]?\\d+)?', text)\n"
            "        opt = float(nums[-1]) if nums else 50.0\n"
            "state['optimal_order'] = float(opt)\n"
        )
        steps[current_step_index] = step
        fixed["steps"] = steps
        return fixed, "已修复当前 code 步骤：兼容 agent 自然语言输出，避免 json.loads 解析失败。"

    # Case 2: Loop not progressing due to missing per-round agent outputs.
    if "loop exceeded max iterations" in err or "agent_order_raw" in code or "demand_sample" in code:
        for st in steps:
            if not isinstance(st, dict) or st.get("type") != "loop":
                continue
            inner = st.get("inner_steps") if isinstance(st.get("inner_steps"), list) else []
            for inner_step in inner:
                if not isinstance(inner_step, dict) or inner_step.get("type") != "code":
                    continue
                snippet = str(inner_step.get("code_snippet") or "")
                if "demand_sample" in snippet and "json.loads" in snippet:
                    inner_step["code_snippet"] = (
                        "import json\n"
                        "import random\n"
                        "raw = state.get('demand_sample', None)\n"
                        "try:\n"
                        "    demand_val = json.loads(str(raw))\n"
                        "except Exception:\n"
                        "    low = float(state.get('demand_low', 0) or 0)\n"
                        "    high = float(state.get('demand_high', 100) or 100)\n"
                        "    demand_val = random.uniform(low, high)\n"
                        "state['realized_demand'] = float(demand_val)\n"
                        "state.setdefault('demand_history', []).append(state['realized_demand'])\n"
                    )
                if "agent_order_raw" in snippet and "json.loads" in snippet:
                    inner_step["code_snippet"] = (
                        "import json\n"
                        "raw = state.get('agent_order_raw', None)\n"
                        "try:\n"
                        "    order_val = json.loads(str(raw))\n"
                        "except Exception:\n"
                        "    order_val = state.get('optimal_order', 0)\n"
                        "state['agent_order'] = float(order_val)\n"
                        "state.setdefault('order_history', []).append(state['agent_order'])\n"
                        "profit_val = float(state.get('price', 0)) * min(float(state.get('realized_demand', 0)), state['agent_order']) - float(state.get('cost', 0)) * state['agent_order']\n"
                        "state['profit'] = profit_val\n"
                        "state.setdefault('profit_history', []).append(profit_val)\n"
                        "state['cumulative_profit'] = float(state.get('cumulative_profit', 0)) + profit_val\n"
                        "state['round'] = int(state.get('round', 0)) + 1\n"
                    )
            st["inner_steps"] = inner
        fixed["steps"] = steps
        return fixed, "已修复 loop 内部解析逻辑：缺失 agent 输出时使用安全默认值，防止循环卡死。"

    return fixed, "未匹配到规则化修复模式，保留原 simulation。"


@router.post("/repair", response_model=SimulationRepairResponse)
async def repair_simulation(req: SimulationRepairRequest, current_user: User = Depends(get_current_user)):
    sim = req.simulation or {}
    if not isinstance(sim, dict):
        raise HTTPException(status_code=400, detail="simulation must be a JSON object")

    repair_prompt = (
        "你是 Simulation 修复代理。请修复当前 simulation JSON，使其可被 /api/simulation/run_step 正常执行。\n"
        "必须输出严格 JSON：{\"fixed_simulation\":{...},\"explanation\":\"...\"}\n"
        "修复规则：\n"
        "1) 保留原有业务意图，最小化修改\n"
        "2) steps 必须是数组，每个 step 要有 id/type\n"
        "3) code 步骤要避免 NameError/KeyError，访问状态用 state['k'] 或 state.get('k')\n"
        "4) agent/dialogue 步骤应保证 agent_ids 为数组\n"
        "5) variables 中 value 必须是字符串\n"
        "6) 如果某步明显报错，可只修复该步及其依赖变量\n"
        f"Current Step Index: {req.current_step_index}\n"
        f"Error: {req.error_message}\n"
        f"World State: {json.dumps(req.world_state, ensure_ascii=False)[:6000]}\n"
        f"History Tail: {json.dumps(req.history[-8:], ensure_ascii=False)[:8000]}\n"
        f"Simulation JSON: {json.dumps(sim, ensure_ascii=False)[:30000]}\n"
    )

    chat_cfg = _resolve_user_chat_config(current_user)

    def _call_ai() -> str:
        res = ai_chat(
            messages_or_prompt=repair_prompt,
            model=chat_cfg.get("model"),
            api_key=chat_cfg.get("api_key"),
            base_url=chat_cfg.get("base_url"),
            temperature=0.2,
            max_tokens=4096,
            timeout_s=120.0,
        )
        if isinstance(res, dict):
            return str(res.get("content") or res)
        return str(res)

    text = _call_ai()
    obj = _extract_json_obj(text)

    fixed = obj.get("fixed_simulation") if isinstance(obj, dict) else None
    explanation = obj.get("explanation") if isinstance(obj, dict) else None

    if not isinstance(fixed, dict):
        fixed, fallback_explanation = _fallback_fix_simulation(sim, req.current_step_index, req.error_message)
        explanation = explanation or fallback_explanation
    if not isinstance(fixed.get("steps"), list):
        fixed["steps"] = sim.get("steps", []) if isinstance(sim.get("steps"), list) else []
    if not isinstance(fixed.get("variables"), list):
        fixed["variables"] = sim.get("variables", []) if isinstance(sim.get("variables"), list) else []

    if "id" in sim:
        fixed["id"] = sim.get("id")
    if "name" in sim:
        fixed["name"] = str(sim.get("name", ""))
    if "description" in sim:
        fixed["description"] = str(sim.get("description", ""))

    normalized_vars = []
    for v in fixed.get("variables", []):
        if not isinstance(v, dict):
            continue
        vv = dict(v)
        vv["key"] = str(vv.get("key", ""))
        vv["description"] = str(vv.get("description", ""))
        vv["value"] = str(vv.get("value", ""))
        normalized_vars.append(vv)
    fixed["variables"] = normalized_vars

    if not explanation:
        explanation = "已自动修复 simulation 配置，可继续运行。"

    return SimulationRepairResponse(fixed_simulation=fixed, explanation=explanation)
