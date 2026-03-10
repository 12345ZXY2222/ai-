#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""批量生成：基于“行为库存管理”报告/参考文献（LLM 实验设想）创建一组可运行 simulations。

目标：把 Reading_Report_BOM_Evolution_CuiEtAl_2025.pdf 中按 Simon(1955)
(Choice/Design/Intelligence activity) 组织的 LLM 实验设想，落地为多个可运行 Simulation。

做法：
- 为每个实验方向准备一个 prompt（强约束可运行、可记录、可汇总）。
- 上传“报告 + 该实验关键参考文献”到 /api/simulations/upload_temp。
- 调用 /api/simulations/generate 让 Architect 生成 simulation。
- 保存到 /api/simulations。
- 做一个小规模 smoke-run（把 rounds/replications 等变量压到很小）并输出质量报告。

用法：
  python scripts/experiments/generate_behavioral_inventory_part3_suite.py --save-artifacts

可选：
  --base-url http://127.0.0.1:8001
  --provider deepseek --model deepseek-chat
  --smoke-rounds 3
  --only newsvendor_pull_to_center,herding_in_queues
  --max-experiments 3
"""

import argparse
import json
import os
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


@dataclass
class Experiment:
	slug: str
	name: str
	activity: str  # Choice / Design / Intelligence
	description: str
	refs: List[Path]
	prompt_body: str


ROOT = Path(__file__).resolve().parents[2]
BOM_DIR = ROOT / "行为库存管理"
REF_DIR = BOM_DIR / "参考文献"
REPORT_PDF = BOM_DIR / "Reading_Report_BOM_Evolution_CuiEtAl_2025.pdf"


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
		"persona": "你是一个用于行为运营/库存管理实验的AI被试（silicon subject）。你必须严格按要求输出 JSON。",
		"long_term_memory": [],
	}
	return _post_json(s, f"{auth.base_url}/api/agents", payload)


def upload_temp_file(auth: Auth, file_path: Path) -> str:
	if not file_path.exists():
		raise FileNotFoundError(str(file_path))

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


def run_simulation_step(
	auth: Auth, step: Dict[str, Any], history: List[Dict[str, Any]], world_state: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
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


def execute_simulation(auth: Auth, sim: Dict[str, Any], max_steps: int = 4000, smoke_rounds: Optional[int] = None) -> Dict[str, Any]:
	steps: List[Dict[str, Any]] = sim.get("steps") or []
	variables: List[Dict[str, Any]] = sim.get("variables") or []

	history: List[Dict[str, Any]] = []
	world_state: Dict[str, Any] = _init_world_state(variables)

	if smoke_rounds is not None:
		for k in [
			"total_rounds",
			"rounds",
			"n_rounds",
			"num_rounds",
			"replications",
			"n_replications",
			"num_replications",
		]:
			if k in world_state:
				try:
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
				if new_items and isinstance(new_items[0].get("content"), str) and new_items[0]["content"].startswith("Error"):
					raise RuntimeError(f"Loop condition error: {new_items[0]['content']}")
				is_true = bool(new_state.get("__loop_result"))
				if "__loop_result" in new_state:
					del new_state["__loop_result"]
				world_state = new_state

			# Implement loop semantics: if condition is true, run inner_steps then
			# re-evaluate the loop condition again (do NOT advance index). If false,
			# exit loop by advancing to the next step.
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


def _walk_steps(steps: List[Dict[str, Any]]):
	for st in steps:
		yield st
		inner = st.get("inner_steps")
		if isinstance(inner, list) and inner:
			yield from _walk_steps(inner)


def force_agent_id(sim: Dict[str, Any], agent_id: str) -> None:
	steps = sim.get("steps") or []
	for st in _walk_steps(steps):
		if st.get("type") == "agent":
			st["agent_ids"] = [agent_id]
			st["agent_id"] = None


def quality_report(sim: Dict[str, Any], run: Optional[Dict[str, Any]]) -> Dict[str, Any]:
	steps = sim.get("steps") or []
	variables = sim.get("variables") or []
	agent_steps = [st for st in _walk_steps(steps) if st.get("type") == "agent"]

	rep: Dict[str, Any] = {
		"name": sim.get("name"),
		"description": sim.get("description"),
		"steps": len(list(_walk_steps(steps))),
		"top_level_steps": len(steps),
		"variables": len(variables),
		"agent_steps": len(agent_steps),
	}

	if run is None:
		rep.update({"executed_steps": 0, "runtime_errors": None, "history_items": 0})
		return rep

	history = run.get("history") or []
	runtime_errors = 0
	for h in history:
		c = h.get("content") if isinstance(h, dict) else None
		if isinstance(c, str) and (c.startswith("Error executing code") or c.startswith("Error:")):
			runtime_errors += 1

	rep.update(
		{
			"executed_steps": run.get("executed_steps"),
			"runtime_errors": runtime_errors,
			"history_items": len(history),
			"final_state_keys": sorted(list((run.get("world_state") or {}).keys()))[:80],
		}
	)
	return rep


def list_saved_simulations(auth: Auth) -> List[Dict[str, Any]]:
	s = requests.Session()
	s.headers.update({"Authorization": f"Bearer {auth.token}"})
	try:
		data = _get_json(s, f"{auth.base_url}/api/simulations")
		return data if isinstance(data, list) else []
	except Exception:
		return []


def _count_runtime_errors(history: List[Dict[str, Any]]) -> int:
	runtime_errors = 0
	for h in history:
		c = h.get("content") if isinstance(h, dict) else None
		if isinstance(c, str) and (c.startswith("Error executing code") or c.startswith("Error:")):
			runtime_errors += 1
	return runtime_errors


def _validate_simulation_syntax_and_safety(sim: Dict[str, Any]) -> List[str]:
	"""Best-effort static checks to avoid common non-runnable patterns."""
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
		# Keeping it simple: disallow function definitions in generated code steps.
		if "def " in low or "lambda " in low:
			issues.append("function_definition_in_code")
		try:
			compile(code, f"<{st.get('id','code')}>", "exec")
		except SyntaxError as e:
			issues.append(f"syntax_error:{e.msg}")
	return sorted(list(set(issues)))


def _suite_experiments() -> List[Experiment]:
	def R(name: str) -> Path:
		return REF_DIR / name

	common_rules = """
HARD REQUIREMENTS (must follow):
- Produce a Simulation JSON with: name, description, variables(list), steps(list).
- Use only Python standard library in code steps. Do NOT use scipy/numpy/pandas.
- Record all trial-level results into state['history'] (a list of dicts).
- At the end, compute state['summary'] with condition-level aggregates.
- Any agent step MUST request STRICT JSON output and your simulation MUST parse it robustly.
- Keep it runnable with the platform engine: steps are executed one by one; loops via inner_steps + repeat_count / loop.

ROBUSTNESS RULES (must follow):
- State/world_state MUST remain JSON-serializable at all times (only None/bool/int/float/str/list/dict).
- NEVER store functions, modules, code objects, or class instances into state.
- Do NOT use eval/exec/compile in any code step.
- Do NOT define helper functions (no 'def' or 'lambda') inside code steps; inline the logic instead.
- In variables: any list/dict value MUST be valid JSON (double quotes). Example: ["baseline","treat"] not ['baseline','treat'].
- In Step 1 init code: set defaults for all keys you later use (e.g., rng_seed, total_rounds, treatments/scenarios lists, indices, history containers).
- Always seed randomness via random.seed(state['rng_seed']).
- Agent outputs may arrive as either a string OR a dict (already parsed). Always do:
	obj = extract_json(last_output)
	if isinstance(obj, str): try json.loads(obj) else keep as string
	if isinstance(obj, dict): read keys from it
	Never call string methods (like .find) on a dict.
- If a required key is missing from the agent JSON, fill a safe default and keep the simulation running.
""".strip()

	return [
		Experiment(
			slug="newsvendor_pull_to_center",
			name="Newsvendor Pull-to-Center + Debias",
			activity="Choice",
			description="Newsvendor 订货偏差（pull-to-center）与去偏处理。",
			refs=[R("Cachon_schweitzer_ms.pdf"), R("bostian_holt_smith_2007.pdf"), R("Ren-OverconfidenceNewsvendorOrders-2013.pdf")],
			prompt_body=f"""
{common_rules}

EXPERIMENT: Newsvendor pull-to-center bias (Schweitzer & Cachon 2000; Bostian et al. 2008) with a debiasing treatment.

Design:
- Two scenarios: low-profit (CR around 0.2) and high-profit (CR around 0.8).
- Two treatments: baseline vs debias.
- Known demand distribution (e.g., Poisson mean=100). Compute optimal order quantity Q* as the CR-quantile.
- Run state['total_rounds'] rounds per condition. Default total_rounds=30.

Implementation details (IMPORTANT, to keep code runnable under constraints):
- DO NOT use def/lambda/eval/exec/compile.
- To compute a Poisson CR-quantile without SciPy, inline a loop using a recurrence for pmf:
	- lam = state['lam'] (e.g. 100)
	- p = math.exp(-lam)  # P(X=0)
	- cdf = p
	- k = 0
	- while cdf < critical_ratio and k < max_k:
		k += 1
		p = p * lam / k
		cdf += p
	- set optimal_order = k
- Choose max_k conservatively (e.g., int(lam + 10*sqrt(lam) + 50)).

Per round record:
- treatment, scenario, round, demand, critical_ratio, optimal_order, order_quantity, deviation, profit.

Debias treatment: add training/feedback/explanation requirement.
At end compute summary per condition: mean deviation, bias direction check.
""".strip(),
		),
		Experiment(
			slug="human_algorithm_naw",
			name="Human-Algorithm Collaboration (NAW)",
			activity="Design",
			description="朴素建议加权（Naïve Advice Weighting）与特征透明度干预。",
			refs=[R("Human-Algorithm Collaboration with Private Information_14b8d3ac-7e23-4a41-8877-8de26238431d.pdf")],
			prompt_body=f"""
{common_rules}

EXPERIMENT: Human-algorithm collaboration with private information (NAW).

Per round:
- True value X ~ Normal(mu, sigma).
- Algorithm forecast A = X + noise_A.
- Private signal P = X + noise_P.
- Agent outputs final forecast F.

Treatments:
- baseline: no transparency.
- transparency: provide extra diagnostic of private signal value.

Metrics:
- implied weight w = (F - A) / (P - A) (handle divide-by-zero).
- squared error (F-X)^2.

Run state['total_rounds'] rounds per treatment (default 20).
Record each round in state['history']: treatment, round, X, A, P, F, w, error.
Summary: mean(w), std(w), MSE by treatment.

Agent output strict JSON: {{"final_forecast": <number>, "reason": "..."}}.
""".strip(),
		),
		Experiment(
			slug="herding_in_queues",
			name="Herding in Queues",
			activity="Intelligence",
			description="队列选择中的从众/羊群效应与后悔提示干预。",
			refs=[R("herding_in_queues.pdf"), R("InfoDisclosure-Herding.pdf")] if (R("InfoDisclosure-Herding.pdf")).exists() else [R("herding_in_queues.pdf")],
			prompt_body=f"""
{common_rules}

EXPERIMENT: Herding in queues with waiting costs.

Per round:
- Two providers A/B with unknown quality QA,QB in [0,1].
- Agent gets private noisy signal about which is better.
- Public info: current queue lengths LA, LB.
- Agent chooses A or B.

Treatments:
- baseline: maximize expected utility (quality benefit - waiting_cost*queue_length).
- regret_prompt: add instruction to minimize ex-post regret.

Record in history: treatment, round, QA, QB, signal, LA, LB, choice, realized_utility, chose_longer_queue, herded_against_signal.
Summary: herding rate, against-signal rate, avg utility.

Agent JSON: {{"choice": "A"|"B", "reason": "..."}}.
""".strip(),
		),
		Experiment(
			slug="confirmation_bias_advertising",
			name="Confirmation Bias in Advertising",
			activity="Intelligence",
			description="确认偏误：先验广告预期如何同化模棱两可体验。",
			refs=[R("Production   Oper Manag - 2020 - Bagchi - Strategic Implications of Confirmation Bias‐Inducing Advertising.pdf")],
			prompt_body=f"""
{common_rules}

EXPERIMENT: Confirmation bias inducing advertising.

Per round:
- True quality Q in [1,10].
- Ad sets expectation E (high vs low).
- Ambiguous experience signal S = Q + noise.
- Agent reports perceived quality R (1-10) and purchase intention (0-1).

Treatments: high_expectation_ad vs low_expectation_ad.
Record: treatment, round, Q, E, S, reported_quality, purchase_intention.
Summary: mean(report-S) and mean(report-Q) by treatment.

Agent JSON: {{"reported_quality": <number>, "purchase_intention": <number>, "reason": "..."}}.
""".strip(),
		),
		Experiment(
			slug="forecasting_service_level_anchor",
			name="Forecasting vs Service Level Anchor",
			activity="Intelligence",
			description="需求预测与服务水平信息导致的隐藏锚点。",
			refs=[R("A_hidden_anchor_The_influence_of_service_levels_on.pdf"), R("Tong_Feiler_-_Behavioral_Model_of_Forecasting_-_Man_Sci_-_2017.pdf")],
			prompt_body=f"""
{common_rules}

EXPERIMENT: Demand forecasting contaminated by service level info (hidden anchor).

Per round:
- True demand D ~ Normal(mu, sigma).
- Agent sees historical samples and predicts most likely demand.
- Also show required service level (0.8 vs 0.95) which should NOT affect the forecast.

Treatments: service_level_low vs service_level_high.
Record: treatment, round, mu, sigma, service_level, forecast.
Summary: mean(forecast-mu) by treatment.

Agent JSON: {{"forecast": <number>, "reason": "..."}}.
""".strip(),
		),
		Experiment(
			slug="response_time_bargaining",
			name="Response Time Information in Bargaining",
			activity="Choice",
			description="谈判中响应时间信息如何改变报价与结果。",
			refs=[R("The_Value_of_Response_Time_Information_in_Supply_C.pdf")],
			prompt_body=f"""
{common_rules}

EXPERIMENT: Bargaining with response time information.

Per episode:
- Retailer proposes wholesale price w.
- Supplier has private cost c and accepts/rejects.
- Response time RT is generated (lower RT = stronger preference). In RT treatment, retailer observes prior RTs.

Treatments: noRT vs RT.
- Simulate multiple episodes; each episode has 5 bargaining rounds.

Record: treatment, episode, round, cost, offer_w, accept, RT, profits.
Summary: accept rate, mean final price, retailer profit by treatment.

Agent JSON for offers: {{"wholesale_price": <number>, "reason": "..."}}.
""".strip(),
		),
		Experiment(
			slug="prospect_theory_pricing_regret",
			name="Pricing Framing (Prospect/Regret)",
			activity="Choice",
			description="同一经济本质不同表述：参考点/损失厌恶/后悔对价格选择的影响。",
			refs=[R("Kahneman-Tversky-Prospect-theory-1979.pdf"), R("Advance_Selling_When_Consumers_Regret.pdf"), R("Nasiry-DynamicPricingLossAverse-2011.pdf")],
			prompt_body=f"""
{common_rules}

EXPERIMENT: Pricing choice under framing/reference point and anticipated regret.

Per round:
- Present two options A/B with same expected value but different framing (gain vs loss; discount vs surcharge; refund vs no-refund).
- Agent chooses A or B.

Treatments: gain_frame vs loss_frame; regret_salient vs regret_not_salient.
Record: treatment, round, choice.
Summary: choice share under each treatment.

Agent JSON: {{"choice": "A"|"B", "reason": "..."}}.

Implementation notes:
- Keep every code_snippet simple and syntactically valid Python (no unterminated quotes; avoid embedding long multi-line strings).
- Prefer short string constants and build any longer text in the agent prompt using JSON-safe escaping.
""".strip(),
		),
		Experiment(
			slug="trust_in_info_sharing",
			name="Trust in Forecast Information Sharing",
			activity="Intelligence",
			description="信息共享中的信任/可信度更新。",
			refs=[R("mnsc.1110.1334.1.pdf"), R("07_23_Communication Media.pdf")] if (R("07_23_Communication Media.pdf")).exists() else [R("mnsc.1110.1334.1.pdf")],
			prompt_body=f"""
{common_rules}

EXPERIMENT: Trust and credibility in forecast information sharing.

Per round:
- Sender sends a cheap-talk forecast message M about demand.
- Receiver (agent) chooses capacity/inventory decision Q based on M.
- Sender reliability varies by treatment.

Treatments: high_reliability vs low_reliability sender history.
Agent outputs decision Q and updated trust score in [0,1].

Record: treatment, round, true_demand, message, decision_Q, trust, realized_profit.
Summary: trust calibration and profit by treatment.

Agent JSON: {{"decision_Q": <number>, "trust": <number>, "reason": "..."}}.
""".strip(),
		),
		Experiment(
			slug="overconfidence_calibration",
			name="Overconfidence & Calibration",
			activity="Intelligence",
			description="过度自信/过度精确：点预测+置信区间校准与反馈。",
			refs=[R("Ren-OverconfidenceNewsvendorOrders-2013.pdf")],
			prompt_body=f"""
{common_rules}

EXPERIMENT: Overconfidence / calibration in probabilistic forecasting.

Per round:
- True value X ~ Normal(mu, sigma).
- Agent sees evidence (samples) and provides point estimate and 90% CI [L,U], plus stated confidence.

Treatments: baseline vs feedback.
Record: treatment, round, X, estimate, lower, upper, covered, confidence.
Summary: coverage rate and calibration error by treatment.

Agent JSON: {{"estimate": <number>, "lower": <number>, "upper": <number>, "confidence": <number>, "reason": "..."}}.
""".strip(),
		),
	]


def build_prompt(exp: Experiment, agent_id: str) -> str:
	return f"""
You are an expert simulation designer.

Create ONE runnable Simulation for the following experiment.

Meta:
- Simulation name must be: {exp.name}
- Tag/slug: {exp.slug}
- Simon(1955) activity class: {exp.activity}

Agent requirement:
- Use EXACTLY this agent_id for ALL agent steps: {agent_id}
- Each agent step must set output_var and your code must parse the agent JSON robustly.

Execution environment notes:
- Code steps run with Python standard library and a helper extract_json(text).
- extract_json may return a dict when it can parse JSON.
- Do NOT assume agent output is always a string; it may already be a dict.

General structure requirement:
- Step 1: code step initializes state variables, seeds RNG, state['history']=[], and sets default total_rounds.
- Then loops over treatments/scenarios as needed, then loops rounds using repeat_count = {{state.total_rounds}} (or equivalent).
- Each round appends ONE record dict into state['history'].
- Final step computes state['summary'].

Critical implementation constraints:
- State/world_state must remain JSON-serializable; do not store functions/modules/code objects in state.
- Do NOT define helper functions (no 'def' or 'lambda') in code steps; inline calculations instead.
- NEVER store python-literal lists in variables (single quotes). Use JSON arrays with double quotes.
- When parsing agent output, do NOT use regex. Use extract_json(last_output) and then type-check.
- If required keys are missing, fill safe defaults so the simulation continues.

Output validity requirements:
- Every code step's code_snippet MUST be valid Python (it must compile).
- Avoid complicated quoting inside code_snippet; keep string literals short and well-formed.

Now implement this experiment:
{exp.prompt_body}
""".strip()


def _select_files(exp: Experiment) -> List[Path]:
	files = [REPORT_PDF]
	for p in exp.refs:
		if p.exists() and p not in files:
			files.append(p)
	return files[:5]


def _ensure_dirs(path: Path) -> None:
	path.mkdir(parents=True, exist_ok=True)


def main() -> int:
	ap = argparse.ArgumentParser()
	ap.add_argument("--base-url", dest="base_url", default=os.environ.get("AISIM_BASE_URL", "http://127.0.0.1:8001"))
	ap.add_argument("--provider", dest="provider", default=os.environ.get("AISIM_PROVIDER", "deepseek"))
	ap.add_argument("--model", dest="model", default=os.environ.get("AISIM_MODEL", "deepseek-chat"))
	ap.add_argument("--llm-base-url", dest="llm_base_url", default=os.environ.get("AISIM_LLM_BASE_URL"))
	ap.add_argument("--api-key", dest="api_key", default=os.environ.get("AISIM_LLM_API_KEY"))
	ap.add_argument("--username", dest="username", default=os.environ.get("AISIM_USER", f"suite_{uuid.uuid4().hex[:8]}"))
	ap.add_argument("--password", dest="password", default=os.environ.get("AISIM_PASS", "pass1234"))
	ap.add_argument("--save-artifacts", action="store_true")
	ap.add_argument("--smoke-rounds", type=int, default=3)
	ap.add_argument("--max-steps", type=int, default=2500)
	ap.add_argument("--only", type=str, default="")
	ap.add_argument("--max-experiments", type=int, default=0)
	ap.add_argument("--max-attempts", type=int, default=3)
	ap.add_argument("--force", action="store_true", help="Regenerate even if a simulation with the same target name already exists")
	args = ap.parse_args()

	if not REPORT_PDF.exists():
		raise FileNotFoundError(f"Missing report: {REPORT_PDF}")

	exps = _suite_experiments()
	if args.only.strip():
		only = {s.strip() for s in args.only.split(",") if s.strip()}
		exps = [e for e in exps if e.slug in only]
	if args.max_experiments and args.max_experiments > 0:
		exps = exps[: args.max_experiments]

	auth = register_and_login(args.base_url, args.username, args.password)
	agent = ensure_template_agent(auth, args.provider, args.model, args.llm_base_url, args.api_key)
	agent_id = agent["id"]
	existing_names = {((s.get("name") or "").strip()) for s in list_saved_simulations(auth)}

	artifacts_root = ROOT / "artifacts" / "results" / "behavioral_inventory_part3_suite"
	ts = time.strftime("%Y%m%d_%H%M%S")
	index: Dict[str, Any] = {
		"timestamp": ts,
		"base_url": args.base_url,
		"provider": args.provider,
		"model": args.model,
		"agent_id": agent_id,
		"smoke_rounds": args.smoke_rounds,
		"experiments": [],
	}

	for exp in exps:
		item: Dict[str, Any] = {"slug": exp.slug, "name": exp.name, "activity": exp.activity, "status": "started", "files": []}
		try:
			target_name = f"BOM-{exp.activity}: {exp.name}".strip()
			if (not args.force) and (target_name in existing_names):
				item["status"] = "skipped_existing"
				item["simulation_name"] = target_name
				index["experiments"].append(item)
				continue

			files = _select_files(exp)
			item["files"] = [str(p.relative_to(ROOT)) for p in files]

			uploaded_names = [upload_temp_file(auth, p) for p in files]
			sim = None
			run = None
			static_issues: List[str] = []
			last_error: Optional[str] = None
			for attempt in range(1, max(1, args.max_attempts) + 1):
				prompt = build_prompt(exp, agent_id)
				prompt += "\n\nSTRICT: No eval/exec/compile. No def/lambda. Keep state JSON-serializable."
				if attempt > 1:
					prompt += f"\nThis is attempt {attempt}. Fix any prior runtime/syntax issues and regenerate a clean simulation."
				sim = generate_simulation(auth, prompt, uploaded_names)

				# Enforce agent_id on all agent steps
				force_agent_id(sim, agent_id)

				sim["name"] = target_name
				sim["description"] = (sim.get("description") or exp.description or "").strip()

				static_issues = _validate_simulation_syntax_and_safety(sim)
				if static_issues:
					last_error = f"static_validation_failed: {', '.join(static_issues[:8])}"
					continue

				try:
					run = execute_simulation(auth, sim, max_steps=args.max_steps, smoke_rounds=args.smoke_rounds)
				except Exception as e:
					last_error = str(e)
					run = None
					continue

				history = (run or {}).get("history") or []
				runtime_errors = _count_runtime_errors(history)
				if runtime_errors == 0:
					break
				last_error = f"smoke_runtime_errors={runtime_errors}"

			# Save best-effort simulation
			if sim is None:
				raise RuntimeError("Generation returned empty simulation")
			saved = save_simulation(auth, sim)
			item["simulation_id"] = saved.get("id")
			item["simulation_name"] = target_name
			existing_names.add(target_name)

			rep = quality_report(sim, run)
			item["status"] = "saved"
			if run is not None:
				item["status"] = "smoke_ran" if (rep.get("runtime_errors") == 0) else "smoke_ran_with_errors"
			else:
				item["status"] = "smoke_failed"
				if last_error:
					item["smoke_error"] = last_error
			item["quality"] = rep

			if args.save_artifacts:
				out_dir = artifacts_root / exp.slug
				_ensure_dirs(out_dir)
				(out_dir / f"sim_{ts}.json").write_text(json.dumps(sim, ensure_ascii=False, indent=2), encoding="utf-8")
				if run is not None:
					(out_dir / f"run_{ts}.json").write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
				(out_dir / f"report_{ts}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

		except Exception as e:
			item["status"] = "failed"
			item["error"] = str(e)

		index["experiments"].append(item)

	if args.save_artifacts:
		_ensure_dirs(artifacts_root)
		(artifacts_root / f"index_{ts}.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

	ok = sum(1 for x in index["experiments"] if x.get("status") in {"saved", "smoke_ran"})
	print(f"Suite done. experiments={len(index['experiments'])} ok={ok}")
	for x in index["experiments"]:
		print(f"- {x['slug']}: {x.get('status')} sim_id={x.get('simulation_id')}")

	return 0


if __name__ == "__main__":
	raise SystemExit(main())
