#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Paper-driven redesign of Behavioral Inventory (Part 3) suite simulations.

Goal
- Use an existing agent (ai1 or fallback) to read reference PDFs (via extracted snippets)
  and output a structured experiment spec per slug.
- Use that spec to generate a new runnable Simulation via /api/simulations/generate.
- Save simulations locally under artifacts/results/<suite-name>/<slug>/sim_<ts>.json
  and persist them into backend via /api/simulations.

Run with backend venv (pypdf is installed there):
  backend/.venv/bin/python scripts/experiments/redesign_behavioral_inventory_part3_suite.py \
	--base-url http://127.0.0.1:8001 --username suite_xxx --password pass1234 \
	--provider deepseek --model deepseek-chat --save-artifacts

Then rerun the suite:
  python scripts/analysis/run_part3_suite_and_report.py \
	--suite-name behavioral_inventory_part3_suite_redesigned \
	--force-use-rag false --smoke-rounds 30

Notes
- The generator endpoint consumes uploaded PDFs for grounding; we additionally embed
  short keyword-focused snippets into the analysis prompt so the spec is auditable.
- We keep code-step constraints strict to avoid backend sandbox / safety checks.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
BOM_DIR = ROOT / "行为库存管理"
REF_DIR = BOM_DIR / "参考文献"
REPORT_PDF = BOM_DIR / "Reading_Report_BOM_Evolution_CuiEtAl_2025.pdf"

DEFAULT_SUITE_NAME = "behavioral_inventory_part3_suite_redesigned"

KEYWORDS = [
	"result",
	"results",
	"conclusion",
	"discussion",
	"experiment",
	"table",
	"figure",
	"treatment",
	"control",
	"hypothesis",
	"bias",
	"effect",
	"study",
]


@dataclass
class Auth:
	base_url: str
	username: str
	password: str
	token: str


SUITE_EXPERIMENTS: List[Dict[str, Any]] = [
	{
		"slug": "confirmation_bias_advertising",
		"title": "Confirmation Bias in Advertising",
		"activity": "Intelligence",
		"refs": [
			"Production   Oper Manag - 2020 - Bagchi - Strategic Implications of Confirmation Bias‐Inducing Advertising.pdf",
		],
	},
	{
		"slug": "forecasting_service_level_anchor",
		"title": "Forecasting vs Service Level Anchor",
		"activity": "Intelligence",
		"refs": [
			"A_hidden_anchor_The_influence_of_service_levels_on.pdf",
			"Tong_Feiler_-_Behavioral_Model_of_Forecasting_-_Man_Sci_-_2017.pdf",
		],
	},
	{
		"slug": "herding_in_queues",
		"title": "Herding in Queues",
		"activity": "Intelligence",
		"refs": [
			"herding_in_queues.pdf",
			"InfoDisclosure-Herding.pdf",
		],
	},
	{
		"slug": "human_algorithm_naw",
		"title": "Human-Algorithm Collaboration (NAW)",
		"activity": "Design",
		"refs": [
			"Human-Algorithm Collaboration with Private Information_14b8d3ac-7e23-4a41-8877-8de26238431d.pdf",
		],
	},
	{
		"slug": "newsvendor_pull_to_center",
		"title": "Newsvendor Pull-to-Center",
		"activity": "Choice",
		"refs": [
			"Cachon_schweitzer_ms.pdf",
			"bostian_holt_smith_2007.pdf",
			"Ren-OverconfidenceNewsvendorOrders-2013.pdf",
		],
	},
	{
		"slug": "overconfidence_calibration",
		"title": "Overconfidence & Calibration",
		"activity": "Intelligence",
		"refs": [
			"Ren-OverconfidenceNewsvendorOrders-2013.pdf",
		],
	},
	{
		"slug": "prospect_theory_pricing_regret",
		"title": "Pricing Framing (Prospect/Regret)",
		"activity": "Choice",
		"refs": [
			"Kahneman-Tversky-Prospect-theory-1979.pdf",
			"Advance_Selling_When_Consumers_Regret.pdf",
			"Nasiry-DynamicPricingLossAverse-2011.pdf",
		],
	},
	{
		"slug": "response_time_bargaining",
		"title": "Response Time Info in Bargaining",
		"activity": "Design",
		"refs": [
			"The_Value_of_Response_Time_Information_in_Supply_C.pdf",
		],
	},
	{
		"slug": "trust_in_info_sharing",
		"title": "Trust in Forecast Information Sharing",
		"activity": "Intelligence",
		"refs": [
			"mnsc.1110.1334.1.pdf",
			"07_23_Communication Media.pdf",
		],
	},
]


def _post_json(session: requests.Session, url: str, payload: Any, timeout: float = 120.0) -> Any:
	r = session.post(url, json=payload, timeout=timeout)
	if r.status_code >= 400:
		raise RuntimeError(f"POST {url} failed: {r.status_code} {r.text}")
	return r.json()


def _get_json(session: requests.Session, url: str, timeout: float = 60.0) -> Any:
	r = session.get(url, timeout=timeout)
	if r.status_code >= 400:
		raise RuntimeError(f"GET {url} failed: {r.status_code} {r.text}")
	return r.json()


def _put_json(session: requests.Session, url: str, payload: Any, timeout: float = 120.0) -> Any:
	r = session.put(url, json=payload, timeout=timeout)
	if r.status_code >= 400:
		raise RuntimeError(f"PUT {url} failed: {r.status_code} {r.text}")
	return r.json()


def register_and_login(base_url: str, username: str, password: str) -> Auth:
	session = requests.Session()
	reg_url = f"{base_url}/api/register"
	try:
		_post_json(session, reg_url, {"username": username, "password": password}, timeout=60)
	except Exception as e:
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


def list_agents(auth: Auth) -> List[Dict[str, Any]]:
	s = requests.Session()
	s.headers.update({"Authorization": f"Bearer {auth.token}"})
	data = _get_json(s, f"{auth.base_url}/api/agents")
	return data if isinstance(data, list) else []


def create_agent(
	auth: Auth,
	*,
	name: str,
	provider: str,
	model: str,
	base_url: Optional[str] = None,
	api_key: Optional[str] = None,
	persona: Optional[str] = None,
) -> Dict[str, Any]:
	s = requests.Session()
	s.headers.update({"Authorization": f"Bearer {auth.token}"})
	payload: Dict[str, Any] = {
		"name": name,
		"provider": provider,
		"model": model,
		"base_url": base_url,
		"api_key": api_key,
		"persona": persona,
		"long_term_memory": [],
	}
	return _post_json(s, f"{auth.base_url}/api/agents", payload, timeout=60.0)


def duplicate_agent(auth: Auth, agent_id: str) -> Dict[str, Any]:
	s = requests.Session()
	s.headers.update({"Authorization": f"Bearer {auth.token}"})
	return _post_json(s, f"{auth.base_url}/api/agents/{agent_id}/duplicate", {})


def update_agent(auth: Auth, agent_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
	s = requests.Session()
	s.headers.update({"Authorization": f"Bearer {auth.token}"})
	return _put_json(s, f"{auth.base_url}/api/agents/{agent_id}", patch)


def chat(auth: Auth, agent_id: str, message: str, temperature: float = 0.2, max_tokens: int = 1800) -> str:
	s = requests.Session()
	s.headers.update({"Authorization": f"Bearer {auth.token}"})
	payload = {
		"agent_id": agent_id,
		"messages": [
			{"role": "user", "content": message},
		],
		"temperature": temperature,
		"max_tokens": max_tokens,
	}
	res = _post_json(s, f"{auth.base_url}/api/chat", payload, timeout=1200)
	if isinstance(res, dict) and isinstance(res.get("content"), str):
		return res["content"]
	return str(res)


def extract_json(text: Any) -> Any:
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


def _extract_pdf_evidence(pdf_path: Path, keywords: List[str], max_pages: int = 60, max_snippets: int = 6) -> List[Dict[str, Any]]:
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
			compact = compact[:1800]
			snippets.append({"page": i + 1, "text": compact})
			if len(snippets) >= max_snippets:
				break
	if not snippets:
		try:
			t0 = (reader.pages[0].extract_text() or "").strip()
		except Exception:
			t0 = ""
		compact = re.sub(r"\s+", " ", t0)[:1800]
		snippets.append({"page": 1, "text": compact or "(PDF 文本抽取失败)"})
	return snippets


def _ensure_dirs(p: Path) -> None:
	p.mkdir(parents=True, exist_ok=True)


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


def _pick_base_agent(agents: List[Dict[str, Any]], hint: str = "ai1") -> Optional[Dict[str, Any]]:
	for a in agents:
		if (a.get("name") or "").strip().lower() == hint.lower():
			return a
	return agents[0] if agents else None


def _build_common_rules() -> str:
	return (
		"\n".join(
			[
				"HARD REQUIREMENTS (must follow):",
				"- Produce a Simulation JSON with: name, description, variables(list), steps(list).",
				"- Use only Python standard library in code steps. Do NOT use scipy/numpy/pandas.",
				"- Record all trial-level results into state['history'] (a list of dicts).",
				"- At the end, compute state['summary'] with condition-level aggregates.",
				"- Any agent step MUST request STRICT JSON output and your simulation MUST parse it robustly.",
				"- Keep it runnable with the platform engine: steps are executed one by one; loops via inner_steps + loop.",
				"",
				"ROBUSTNESS RULES (must follow):",
				"- State/world_state MUST remain JSON-serializable at all times (only None/bool/int/float/str/list/dict).",
				"- NEVER store functions, modules, code objects, or class instances into state.",
				"- Do NOT use eval/exec/compile in any code step.",
				"- Do NOT define helper functions (no 'def' or 'lambda') inside code steps; inline the logic instead.",
				"- In variables: any list/dict value MUST be valid JSON (double quotes).",
				"- Always seed randomness via random.seed(state['rng_seed']).",
				"- Agent outputs may arrive as either a string OR a dict (already parsed). Always parse robustly.",
				"",
				"OUTPUT CONTRACT:",
				"- state['history'] must contain one dict per trial with keys: treatment/scenario/round plus metrics.",
				"- state['summary'] must be a dict keyed by condition with means + n.",
			]
		)
	).strip()


def build_analysis_prompt(title: str, slug: str, refs: List[Path], evidence_by_file: Dict[str, List[Dict[str, Any]]]) -> str:
	payload = {
		"slug": slug,
		"title": title,
		"files": [p.name for p in refs],
		"evidence": evidence_by_file,
	}
	return (
		"你是行为运营管理（BOM）领域的研究助理。请基于我提供的论文摘录，提炼出可复现实验的设计规格（spec），用于在一个 step-by-step simulation 引擎中实现。\n\n"
		"你必须输出严格 JSON（不要额外文本），字段如下：\n"
		"{\n"
		"  \"paper_question\": \"...\",\n"
		"  \"treatments\": [\"...\"],\n"
		"  \"conditions\": [{\"treatment\":\"...\",\"scenario\":\"...\"}],\n"
		"  \"task\": {\"instructions\":\"...\",\"inputs_per_trial\":[\"...\"],\"outputs_per_trial\":[\"...\"]},\n"
		"  \"incentives\": \"...\",\n"
		"  \"recommended_rounds\": 30,\n"
		"  \"metrics\": [\"...\"],\n"
		"  \"expected_directional_conclusions\": [\"...\"],\n"
		"  \"notes_for_simulation\": [\"...\"]\n"
		"}\n\n"
		"要求：\n"
		"- 不要编造无法从摘录支持的细节；不确定就写 notes。\n"
		"- treatments/conditions 要足够明确以便做对比统计。\n"
		"- recommended_rounds 给出你建议的每条件 trial 数量（整数）。\n\n"
		f"论文摘录输入：\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
	)


def build_architect_prompt(common_rules: str, title: str, activity: str, slug: str, spec: Dict[str, Any]) -> str:
	return (
		f"{common_rules}\n\n"
		f"EXPERIMENT TITLE: {title}\n"
		f"ACTIVITY: {activity}\n"
		f"SLUG: {slug}\n\n"
		"PAPER-DERIVED SPEC (JSON):\n"
		f"{json.dumps(spec, ensure_ascii=False, indent=2)}\n\n"
		"IMPLEMENTATION REQUIREMENTS:\n"
		"- Use treatments/scenarios exactly as spec.treatments / spec.conditions.\n"
		"- Use state['total_rounds'] default = spec.recommended_rounds (but allow override by runner).\n"
		"- Each trial record MUST include: treatment, scenario, round, plus all spec.metrics when applicable.\n"
		"- At end compute summary per condition: mean of numeric metrics, and n.\n"
		"- Keep agent prompts short and deterministic: request STRICT JSON with numeric fields.\n"
		"- Set use_rag=false for agent steps by default (clean slate), unless spec explicitly requires memory.\n"
		"- Do not include the entire PDF text in variables. Only store minimal needed constants.\n"
	).strip()


def main() -> int:
	ap = argparse.ArgumentParser()
	ap.add_argument("--base-url", default=os.environ.get("AISIM_BASE_URL", "http://127.0.0.1:8001"))
	ap.add_argument("--provider", default=os.environ.get("AISIM_PROVIDER", "deepseek"))
	ap.add_argument("--model", default=os.environ.get("AISIM_MODEL", "deepseek-chat"))
	ap.add_argument("--llm-base-url", default=os.environ.get("AISIM_LLM_BASE_URL"))
	ap.add_argument("--api-key", default=os.environ.get("AISIM_LLM_API_KEY"))
	ap.add_argument("--username", default=os.environ.get("AISIM_USER", f"suite_{uuid.uuid4().hex[:8]}"))
	ap.add_argument("--password", default=os.environ.get("AISIM_PASS", "pass1234"))
	ap.add_argument("--suite-name", default=os.environ.get("AISIM_SUITE_NAME", DEFAULT_SUITE_NAME))
	ap.add_argument("--max-pages", type=int, default=int(os.environ.get("AISIM_PDF_MAX_PAGES", "60")))
	ap.add_argument("--max-snippets", type=int, default=int(os.environ.get("AISIM_PDF_MAX_SNIPPETS", "6")))
	ap.add_argument("--max-attempts", type=int, default=int(os.environ.get("AISIM_MAX_ATTEMPTS", "3")))
	ap.add_argument("--only", type=str, default=os.environ.get("AISIM_ONLY", ""))
	ap.add_argument("--save-artifacts", action="store_true")
	args = ap.parse_args()

	auth = register_and_login(args.base_url, args.username, args.password)

	if not REPORT_PDF.exists():
		raise FileNotFoundError(f"Missing report: {REPORT_PDF}")

	agents = list_agents(auth)
	base_agent = _pick_base_agent(agents, hint="ai1")
	persona = (
		"你是严谨的论文复现实验设计师。你的任务是从证据摘录中提炼实验 spec（结构化 JSON），"
		"并且避免编造无证据细节。"
	)

	if base_agent:
		analysis_agent = duplicate_agent(auth, base_agent["id"])
		analysis_agent_id = analysis_agent["id"]
		update_agent(
			auth,
			analysis_agent_id,
			{
				"name": f"ai1复制体-重设实验-{time.strftime('%Y%m%d_%H%M%S')}",
				"persona": persona,
			},
		)
	else:
		created = create_agent(
			auth,
			name=f"paper-redesign-agent-{time.strftime('%Y%m%d_%H%M%S')}",
			provider=args.provider,
			model=args.model,
			base_url=args.llm_base_url,
			api_key=args.api_key,
			persona=persona,
		)
		analysis_agent_id = created["id"]

	suite_dir = ROOT / "artifacts" / "results" / args.suite_name
	_ensure_dirs(suite_dir)

	ts = time.strftime("%Y%m%d_%H%M%S")
	index: Dict[str, Any] = {
		"timestamp": ts,
		"suite_name": args.suite_name,
		"base_url": args.base_url,
		"analysis_agent_id": analysis_agent_id,
		"experiments": [],
	}

	exps = SUITE_EXPERIMENTS
	if args.only.strip():
		only = {s.strip() for s in args.only.split(",") if s.strip()}
		exps = [e for e in exps if e["slug"] in only]

	common_rules = _build_common_rules()

	for exp in exps:
		slug = exp["slug"]
		title = exp["title"]
		activity = exp.get("activity") or ""
		item: Dict[str, Any] = {"slug": slug, "title": title, "status": "started", "files": []}
		try:
			ref_paths: List[Path] = []
			ref_paths.append(REPORT_PDF)
			for fn in exp.get("refs") or []:
				p = REF_DIR / fn
				if p.exists():
					ref_paths.append(p)

			if not ref_paths:
				raise FileNotFoundError("No reference PDFs found")

			item["files"] = [str(p.relative_to(ROOT)) for p in ref_paths]

			evidence_by_file: Dict[str, List[Dict[str, Any]]] = {}
			for p in ref_paths:
				evidence_by_file[p.name] = _extract_pdf_evidence(
					p,
					KEYWORDS,
					max_pages=args.max_pages,
					max_snippets=args.max_snippets,
				)

			analysis_prompt = build_analysis_prompt(title, slug, ref_paths, evidence_by_file)
			spec_raw = chat(auth, analysis_agent_id, analysis_prompt, temperature=0.2, max_tokens=1800)
			spec_obj = extract_json(spec_raw)
			if not isinstance(spec_obj, dict):
				raise RuntimeError("analysis_spec_not_json")

			item["spec"] = spec_obj

			uploaded_names = [upload_temp_file(auth, p) for p in ref_paths]

			target_name = f"BOM-Redesigned-{activity}: {title}".strip()
			prompt = build_architect_prompt(common_rules, title, activity, slug, spec_obj)

			sim: Optional[Dict[str, Any]] = None
			last_error: Optional[str] = None
			for attempt in range(1, max(1, args.max_attempts) + 1):
				prompt_attempt = prompt
				if attempt > 1:
					prompt_attempt += f"\n\nThis is attempt {attempt}. Fix any prior runtime/syntax issues and regenerate a clean simulation."
					if last_error:
						prompt_attempt += f"\nPrior error: {last_error}"

				sim = generate_simulation(auth, prompt_attempt, uploaded_names)
				if not isinstance(sim, dict):
					last_error = "generate_returned_non_dict"
					continue

				sim["name"] = target_name
				sim["description"] = (sim.get("description") or "").strip() or f"Redesigned from papers for {slug}."

				issues = _validate_simulation_syntax_and_safety(sim)
				if issues:
					last_error = f"static_validation_failed: {', '.join(issues[:8])}"
					sim = None
					continue
				break

			if sim is None:
				raise RuntimeError(last_error or "generation_failed")

			saved = save_simulation(auth, sim)
			item["simulation_id"] = saved.get("id")
			item["simulation_name"] = saved.get("name")
			item["status"] = "saved"

			if args.save_artifacts:
				out_dir = suite_dir / slug
				_ensure_dirs(out_dir)
				(out_dir / f"spec_{ts}.json").write_text(json.dumps(spec_obj, ensure_ascii=False, indent=2), encoding="utf-8")
				(out_dir / f"sim_{ts}.json").write_text(json.dumps(sim, ensure_ascii=False, indent=2), encoding="utf-8")

		except Exception as e:
			item["status"] = "failed"
			item["error"] = str(e)

		index["experiments"].append(item)

	(suite_dir / f"index_{ts}.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
	print("DONE")
	print(f"suite_dir={suite_dir}")
	print(f"index={suite_dir / f'index_{ts}.json'}")
	print(f"analysis_agent_id={analysis_agent_id}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())