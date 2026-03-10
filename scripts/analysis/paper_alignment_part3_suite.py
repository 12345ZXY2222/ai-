#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Compare Part 3 suite simulation exports against the referenced papers.

This script:
- Loads the latest exports under artifacts/exports/behavioral_inventory_part3_suite/<ts>/<slug>/
- Extracts keyword-focused evidence snippets from the provided reference PDFs
- Uses an agent (a duplicate of your existing agent) to summarize: (a) how the paper presents results,
  (b) expected directional conclusions
- Computes matching metrics from our exported results
- Appends a paper-alignment section into the latest report markdown

Run with backend venv (pypdf is installed there):
  backend/.venv/bin/python scripts/analysis/paper_alignment_part3_suite.py \
    --base-url http://127.0.0.1:8001 --username suite_xxx --password pass1234

Notes:
- Chat endpoint does not natively consume uploaded files; we embed extracted snippets into the prompt.
- This is a lightweight alignment check (directional consistency), not a strict statistical replication.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUITE_NAME = "behavioral_inventory_part3_suite"
EXPORTS_ROOT = ROOT / "artifacts" / "exports" / DEFAULT_SUITE_NAME
REPORTS_ROOT = ROOT / "artifacts" / "reports" / DEFAULT_SUITE_NAME
BOM_DIR = ROOT / "行为库存管理"
REF_DIR = BOM_DIR / "参考文献"
REPORT_PDF = BOM_DIR / "Reading_Report_BOM_Evolution_CuiEtAl_2025.pdf"


@dataclass
class Auth:
    base_url: str
    token: str


SUITE_EXPERIMENTS: List[Dict[str, Any]] = [
    {
        "slug": "confirmation_bias_advertising",
        "title": "Confirmation Bias in Advertising",
        "refs": [
            "Production   Oper Manag - 2020 - Bagchi - Strategic Implications of Confirmation Bias‐Inducing Advertising.pdf",
        ],
        "expected_metrics": ["reported_quality", "purchase_intention"],
        "group_field": "treatment",
    },
    {
        "slug": "forecasting_service_level_anchor",
        "title": "Forecasting vs Service Level Anchor",
        "refs": [
            "A_hidden_anchor_The_influence_of_service_levels_on.pdf",
            "Tong_Feiler_-_Behavioral_Model_of_Forecasting_-_Man_Sci_-_2017.pdf",
        ],
        "expected_metrics": ["forecast", "mu", "forecast_error"],
        "group_field": "treatment",
    },
    {
        "slug": "herding_in_queues",
        "title": "Herding in Queues",
        "refs": [
            "herding_in_queues.pdf",
            "InfoDisclosure-Herding.pdf",
        ],
        "expected_metrics": ["choice", "chose_longer_queue", "herded_against_signal"],
        "group_field": "treatment",
    },
    {
        "slug": "human_algorithm_naw",
        "title": "Human-Algorithm Collaboration (NAW)",
        "refs": [
            "Human-Algorithm Collaboration with Private Information_14b8d3ac-7e23-4a41-8877-8de26238431d.pdf",
        ],
        "expected_metrics": ["w", "error_sq"],
        "group_field": "treatment",
    },
    {
        "slug": "newsvendor_pull_to_center",
        "title": "Newsvendor Pull-to-Center + Debias",
        "refs": [
            "Cachon_schweitzer_ms.pdf",
            "bostian_holt_smith_2007.pdf",
            "Ren-OverconfidenceNewsvendorOrders-2013.pdf",
        ],
        "expected_metrics": ["order_quantity", "optimal_order", "deviation", "profit"],
        "group_field": "treatment",
    },
    {
        "slug": "overconfidence_calibration",
        "title": "Overconfidence & Calibration",
        "refs": [
            "Ren-OverconfidenceNewsvendorOrders-2013.pdf",
        ],
        "expected_metrics": ["covered", "confidence"],
        "group_field": "treatment",
    },
    {
        "slug": "prospect_theory_pricing_regret",
        "title": "Pricing Framing (Prospect/Regret)",
        "refs": [
            "Kahneman-Tversky-Prospect-theory-1979.pdf",
            "Advance_Selling_When_Consumers_Regret.pdf",
            "Nasiry-DynamicPricingLossAverse-2011.pdf",
        ],
        "expected_metrics": ["choice", "scenario"],
        "group_field": "treatment",
    },
    {
        "slug": "response_time_bargaining",
        "title": "Response Time Information in Bargaining",
        "refs": [
            "The_Value_of_Response_Time_Information_in_Supply_C.pdf",
        ],
        "expected_metrics": ["accept", "offer_w", "response_time", "retailer_profit", "supplier_profit"],
        "group_field": "treatment",
    },
    {
        "slug": "trust_in_info_sharing",
        "title": "Trust in Forecast Information Sharing",
        "refs": [
            "mnsc.1110.1334.1.pdf",
            "07_23_Communication Media.pdf",
        ],
        "expected_metrics": ["trust", "decision_Q", "realized_profit"],
        "group_field": "treatment",
    },
]


KEYWORDS = [
    "result",
    "results",
    "conclusion",
    "conclusions",
    "discussion",
    "experiment",
    "experiments",
    "table",
    "figure",
    "hypothesis",
    "effect",
    "treatment",
    "baseline",
]


def _latest_subdir(path: Path) -> Path:
    subs = [p for p in path.iterdir() if p.is_dir()]
    if not subs:
        raise FileNotFoundError(f"No subdirectories under {path}")
    return sorted(subs, key=lambda p: p.name)[-1]


def _find_latest_report(reports_root: Path = REPORTS_ROOT) -> Path:
    reports = sorted(reports_root.glob("report_*.md"), key=lambda p: p.name)
    if not reports:
        raise FileNotFoundError(f"No reports under {reports_root}")
    return reports[-1]


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


def _get_json(s: requests.Session, url: str, timeout: float = 60.0) -> Any:
    r = s.get(url, timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"GET {url} failed: {r.status_code} {r.text}")
    return r.json()


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


def _extract_pdf_evidence(pdf_path: Path, keywords: List[str], max_pages: int = 60, max_snippets: int = 6) -> List[Dict[str, Any]]:
    reader = PdfReader(str(pdf_path))
    snippets: List[Dict[str, Any]] = []
    for i, page in enumerate(reader.pages[:max_pages]):
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            # Some PDFs trigger extractor edge-cases; skip the page.
            continue
        if not text:
            continue
        low = text.lower()
        if any(k in low for k in keywords):
            # keep it short and stable
            compact = re.sub(r"\s+", " ", text)
            compact = compact[:1800]
            snippets.append({"page": i + 1, "text": compact})
            if len(snippets) >= max_snippets:
                break
    if not snippets:
        # fallback: first page
        try:
            t0 = (reader.pages[0].extract_text() or "").strip()
        except Exception:
            t0 = ""
        compact = re.sub(r"\s+", " ", t0)[:1800]
        snippets.append({"page": 1, "text": compact or "(PDF 文本抽取失败：该文件可能为扫描版或含特殊字体编码)"})
    return snippets


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text("utf-8"))


def _read_history_rows(slug_dir: Path) -> List[Dict[str, Any]]:
    # prefer history.json for schema stability
    hp = slug_dir / "history.json"
    if hp.exists():
        return _read_json(hp)
    # fallback to world_state
    wp = slug_dir / "world_state.json"
    ws = _read_json(wp)
    return ws.get("history") or []


def _group_mean(rows: List[Dict[str, Any]], group_field: str, numeric_fields: List[str]) -> Dict[str, Dict[str, float]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        g = r.get(group_field)
        if g is None:
            continue
        buckets.setdefault(str(g), []).append(r)

    out: Dict[str, Dict[str, float]] = {}
    for g, br in buckets.items():
        stats: Dict[str, float] = {"n": float(len(br))}
        for f in numeric_fields:
            vals: List[float] = []
            for rr in br:
                v = rr.get(f)
                if isinstance(v, (int, float)):
                    vals.append(float(v))
                elif isinstance(v, str):
                    try:
                        vals.append(float(v))
                    except Exception:
                        pass
            if vals:
                stats[f] = sum(vals) / len(vals)
        out[g] = stats
    return out


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    # best-effort: find first {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        cand = text[start : end + 1]
        try:
            return json.loads(cand)
        except Exception:
            return None
    return None


def _ensure_agent_duplicate(auth: Auth, base_agent_name_hint: str = "ai1") -> Dict[str, Any]:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth.token}"})

    agents = _get_json(s, f"{auth.base_url}/api/agents")
    if not isinstance(agents, list) or not agents:
        raise RuntimeError("No agents found; create one first.")

    # Try to locate ai1; fallback to first.
    base_agent = None
    for a in agents:
        nm = (a.get("name") or "").lower()
        if base_agent_name_hint.lower() in nm:
            base_agent = a
            break
    if base_agent is None:
        base_agent = agents[0]

    dup = _post_json(s, f"{auth.base_url}/api/agents/{base_agent['id']}/duplicate", {})

    # Rename to make it explicit
    new_name = f"ai1复制体-论文对照分析-{time.strftime('%Y%m%d_%H%M%S')}"
    upd = _put_json(s, f"{auth.base_url}/api/agents/{dup['id']}", {"name": new_name})
    return upd


def _agent_chat(auth: Auth, agent_id: str, messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 1800) -> Dict[str, Any]:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth.token}"})
    payload = {"agent_id": agent_id, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    return _post_json(s, f"{auth.base_url}/api/chat", payload, timeout=300)


def _summarize_expected_from_paper(auth: Auth, agent_id: str, exp: Dict[str, Any], paper_evidence: Dict[str, Any], our_stats: Dict[str, Any]) -> Dict[str, Any]:
    refs = exp["refs"]
    evidence_txt = json.dumps(paper_evidence, ensure_ascii=False)
    stats_txt = json.dumps(our_stats, ensure_ascii=False)

    prompt = f"""
你是严谨的行为运营管理/供应链管理研究助理。

任务：基于【给定证据摘录】总结论文对这个实验的：
1) 结果呈现方式（例如：用什么指标/表格/图展示，比较哪些 treatment）
2) 论文的主要结论/方向性结论（A > B、提升/降低等）
3) 将【我们的模拟统计】与论文结论对照：是否方向一致？如果不一致，可能原因（模拟简化、样本量小、LLM随机性等）

必须严格输出 JSON（不要输出多余文字），结构：
{{
  "paper_presentation": "...",
  "paper_conclusions": ["...", "..."],
  "alignment": {{"is_consistent": true/false, "why": "..."}},
  "citations": [{{"file": "...pdf", "pages": [1,2], "quote": "..."}}]
}}

实验：{exp['slug']} / {exp['title']}
参考文献文件名：{refs}

【给定证据摘录】（由 PDF 抽取，包含 page 字段）：
{evidence_txt}

【我们的模拟统计】（从导出结果计算的分组均值/占比等）：
{stats_txt}
""".strip()

    res = _agent_chat(
        auth,
        agent_id,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=2000,
    )
    content = res.get("content") if isinstance(res, dict) else str(res)
    obj = _extract_json_from_text(str(content))
    if not obj:
        return {
            "paper_presentation": "(LLM 输出未能解析为 JSON)",
            "paper_conclusions": [],
            "alignment": {"is_consistent": False, "why": "LLM 输出格式错误"},
            "citations": [],
            "raw": str(content)[:2000],
        }
    return obj


def _render_md_block(exp: Dict[str, Any], our_stats: Dict[str, Any], llm_summary: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"### 论文对照：{exp['title']}（{exp['slug']}）")
    lines.append("")
    lines.append("- 参考文献：")
    lines.extend([f"  - {REF_DIR.name}/{r}" for r in exp["refs"]])
    lines.append("- 我们的导出统计（简表）：")
    lines.append("```json")
    lines.append(json.dumps(our_stats, ensure_ascii=False, indent=2)[:6000])
    lines.append("```")
    lines.append("- 论文结果呈现方式（LLM 摘要）：")
    lines.append(f"  - {llm_summary.get('paper_presentation','')}")
    lines.append("- 论文主要结论（LLM 摘要）：")
    for c in llm_summary.get("paper_conclusions") or []:
        lines.append(f"  - {c}")
    align = llm_summary.get("alignment") or {}
    lines.append("- 对照结论（基于我们的模拟统计 vs 论文结论）：")
    lines.append(f"  - 是否方向一致：{bool(align.get('is_consistent'))}")
    if align.get("why"):
        lines.append(f"  - 解释：{align.get('why')}")
    cits = llm_summary.get("citations") or []
    if cits:
        lines.append("- 证据引用（来自你提供的 PDF 摘录）：")
        for cit in cits[:6]:
            file = cit.get("file")
            pages = cit.get("pages")
            quote = (cit.get("quote") or "").strip()
            pages_str = ""
            if isinstance(pages, list) and pages:
                pages_str = " pages=" + ",".join(str(p) for p in pages[:8])
            if file:
                lines.append(f"  - {file}{pages_str}: {quote[:220]}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("AISIM_BASE_URL", "http://127.0.0.1:8001"))
    ap.add_argument("--username", default=os.environ.get("AISIM_USER", "suite_c5a918aa"))
    ap.add_argument("--password", default=os.environ.get("AISIM_PASS", "pass1234"))
    ap.add_argument(
        "--suite-name",
        default=os.environ.get("AISIM_SUITE_NAME", DEFAULT_SUITE_NAME),
        help="Suite name under artifacts/exports and artifacts/reports",
    )
    ap.add_argument(
        "--exports-root",
        default=os.environ.get("AISIM_EXPORTS_ROOT", ""),
        help="Override exports root dir (defaults to artifacts/exports/<suite-name>)",
    )
    ap.add_argument(
        "--reports-root",
        default=os.environ.get("AISIM_REPORTS_ROOT", ""),
        help="Override reports root dir (defaults to artifacts/reports/<suite-name>)",
    )
    ap.add_argument("--exports-ts", default="", help="Override exports timestamp dir (e.g. 20260205_183128)")
    ap.add_argument("--report", default="", help="Override report md path")
    args = ap.parse_args()

    exports_root = Path(args.exports_root) if args.exports_root.strip() else (ROOT / "artifacts" / "exports" / args.suite_name)
    reports_root = Path(args.reports_root) if args.reports_root.strip() else (ROOT / "artifacts" / "reports" / args.suite_name)

    exports_ts_dir = exports_root / args.exports_ts if args.exports_ts else _latest_subdir(exports_root)
    report_path = Path(args.report) if args.report else _find_latest_report(reports_root)

    auth = _login(args.base_url, args.username, args.password)

    # Duplicate agent (ai1 copy). If no ai1, duplicates the first available agent.
    agent = _ensure_agent_duplicate(auth, base_agent_name_hint="ai1")
    agent_id = agent["id"]

    blocks: List[str] = []
    blocks.append("## 5. 论文结果呈现与结论对照（自动分析）")
    blocks.append("")
    blocks.append(f"分析时间：{time.strftime('%Y%m%d_%H%M%S')}")
    blocks.append(f"使用导出目录：{exports_ts_dir}")
    blocks.append(f"使用 Agent：{agent.get('name')} ({agent_id})")
    blocks.append("")

    for exp in SUITE_EXPERIMENTS:
        slug = exp["slug"]
        slug_dir = exports_ts_dir / slug
        if not slug_dir.exists():
            blocks.append(f"### 论文对照：{exp['title']}（{slug}）")
            blocks.append(f"- 缺失导出目录：{slug_dir}")
            blocks.append("")
            continue

        rows = _read_history_rows(slug_dir)
        group_field = exp.get("group_field") or "treatment"
        numeric_fields = [f for f in exp.get("expected_metrics") or [] if f not in ("choice", "scenario")]
        means = _group_mean(rows, group_field, numeric_fields)

        # include simple choice share if present
        choice_share: Dict[str, float] = {}
        if rows and any("choice" in r for r in rows):
            counts: Dict[str, int] = {}
            for r in rows:
                ch = r.get("choice")
                if isinstance(ch, str) and ch:
                    counts[ch] = counts.get(ch, 0) + 1
            total = sum(counts.values())
            if total > 0:
                choice_share = {k: v / total for k, v in sorted(counts.items())}

        our_stats = {
            "slug": slug,
            "n_rows": len(rows),
            "group_field": group_field,
            "group_means": means,
        }
        if choice_share:
            our_stats["choice_share"] = choice_share

        # PDF evidence snippets
        paper_evidence: Dict[str, Any] = {
            "report": {"file": REPORT_PDF.name, "snippets": _extract_pdf_evidence(REPORT_PDF, KEYWORDS, max_pages=30, max_snippets=2)},
            "refs": [],
        }
        for ref in exp["refs"]:
            p = REF_DIR / ref
            if p.exists():
                paper_evidence["refs"].append({"file": ref, "snippets": _extract_pdf_evidence(p, KEYWORDS, max_pages=80, max_snippets=6)})
            else:
                paper_evidence["refs"].append({"file": ref, "missing": True})

        llm_summary = _summarize_expected_from_paper(auth, agent_id, exp, paper_evidence, our_stats)
        blocks.append(_render_md_block(exp, our_stats, llm_summary))

    md_append = "\n".join(blocks).strip() + "\n"
    original = report_path.read_text("utf-8")
    if "## 5. 论文结果呈现与结论对照（自动分析）" in original:
        # replace previous auto section
        new_text = re.sub(
            r"\n## 5\. 论文结果呈现与结论对照（自动分析）[\s\S]*$",
            "\n" + md_append,
            original,
            flags=re.M,
        )
    else:
        new_text = original.rstrip() + "\n\n" + md_append
    report_path.write_text(new_text, "utf-8")

    print(f"updated_report={report_path}")
    print(f"exports_dir={exports_ts_dir}")
    print(f"agent_id={agent_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
