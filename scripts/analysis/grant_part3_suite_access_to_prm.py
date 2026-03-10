#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Grant 'prm' access to the newly created Part3 suite simulations.

This platform currently scopes simulations strictly by `user_id` and does not
provide a built-in sharing/ACL API. So the practical way to "give permissions"
without backend changes is to COPY the simulations into the target user's
account via the existing `/api/simulations` create endpoint.

What it does:
- Reads the latest `sim_*.json` per slug from:
  artifacts/results/behavioral_inventory_part3_suite/<slug>/
- Logs in as the target user (default: prm, pass: pass1234; auto-registers).
- Creates (copies) each simulation for that user.
- Writes an index of created IDs to:
  artifacts/results/behavioral_inventory_part3_suite/grants/grant_<ts>.json

Usage:
  python scripts/analysis/grant_part3_suite_access_to_prm.py --base-url http://127.0.0.1:8001

Optional:
  --username prm --password pass1234
  --name-prefix "(shared) "
  --only confirmation_bias_advertising,newsvendor_pull_to_center
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


ROOT = Path(__file__).resolve().parents[2]
SUITE_ROOT = ROOT / "artifacts" / "results" / "behavioral_inventory_part3_suite"


def _post_json(session: requests.Session, url: str, payload: Dict[str, Any], timeout: float = 60.0) -> Dict[str, Any]:
    r = session.post(url, json=payload, timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"POST {url} failed: {r.status_code} {r.text}")
    return r.json()


def register_and_login(base_url: str, username: str, password: str) -> str:
    session = requests.Session()

    reg_url = f"{base_url}/api/register"
    try:
        _post_json(session, reg_url, {"username": username, "password": password})
    except Exception:
        # ok if already exists
        pass

    token_url = f"{base_url}/api/token"
    r = session.post(
        token_url,
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Login failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


def _suite_slugs() -> List[str]:
    if not SUITE_ROOT.exists():
        return []
    slugs: List[str] = []
    for p in SUITE_ROOT.iterdir():
        if p.is_dir() and not p.name.startswith("__") and p.name not in {"grants"}:
            # slug dirs are expected to have sim_*.json
            if list(p.glob("sim_*.json")):
                slugs.append(p.name)
    return sorted(slugs)


def _latest_sim_path_for_slug(slug: str) -> Path:
    d = SUITE_ROOT / slug
    sims = sorted(d.glob("sim_*.json"))
    if not sims:
        raise FileNotFoundError(f"No sim_*.json under {d}")
    return sims[-1]


def _normalize_sim_payload(sim: Dict[str, Any], name_prefix: str = "") -> Dict[str, Any]:
    name = (sim.get("name") or "Generated Simulation").strip()
    if name_prefix:
        name = f"{name_prefix}{name}"

    payload: Dict[str, Any] = {
        "name": name,
        "description": (sim.get("description") or "").strip(),
        "steps": sim.get("steps") or [],
        "variables": sim.get("variables") or [],
    }

    # Ensure variables values are strings (backend model expects Dict[str,str]).
    norm_vars: List[Dict[str, str]] = []
    for v in payload["variables"]:
        if not isinstance(v, dict):
            continue
        vv: Dict[str, str] = {}
        for k, val in v.items():
            if val is None:
                vv[str(k)] = ""
            elif isinstance(val, str):
                vv[str(k)] = val
            else:
                try:
                    vv[str(k)] = json.dumps(val, ensure_ascii=False)
                except Exception:
                    vv[str(k)] = str(val)
        # drop entries with no key
        if not vv.get("key"):
            continue
        norm_vars.append(vv)
    payload["variables"] = norm_vars

    return payload


def create_simulation(base_url: str, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})
    url = f"{base_url}/api/simulations"
    r = s.post(url, json=payload, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"Create simulation failed: {r.status_code} {r.text}")
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("AISIM_BASE_URL", "http://127.0.0.1:8001"))
    ap.add_argument("--username", default="prm")
    ap.add_argument("--password", default=os.environ.get("PRM_PASS", "pass1234"))
    ap.add_argument("--name-prefix", default="")
    ap.add_argument("--only", type=str, default="")
    args = ap.parse_args()

    slugs = _suite_slugs()
    if args.only.strip():
        only = {s.strip() for s in args.only.split(",") if s.strip()}
        slugs = [s for s in slugs if s in only]

    if not slugs:
        raise RuntimeError(f"No suite slugs found under {SUITE_ROOT}")

    token = register_and_login(args.base_url, args.username, args.password)

    ts = time.strftime("%Y%m%d_%H%M%S")
    grant_dir = SUITE_ROOT / "grants"
    grant_dir.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []

    for slug in slugs:
        sim_path = _latest_sim_path_for_slug(slug)
        sim = json.loads(sim_path.read_text(encoding="utf-8"))
        payload = _normalize_sim_payload(sim, name_prefix=args.name_prefix)

        created = create_simulation(args.base_url, token, payload)
        results.append(
            {
                "slug": slug,
                "source_sim_path": str(sim_path.relative_to(ROOT)),
                "target_username": args.username,
                "created_simulation_id": created.get("id"),
                "created_simulation_name": created.get("name"),
            }
        )

    out = {
        "timestamp": ts,
        "base_url": args.base_url,
        "target_username": args.username,
        "count": len(results),
        "items": results,
    }
    out_path = grant_dir / f"grant_{ts}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"OK: copied {len(results)} simulations to user={args.username}")
    print(f"grant_index={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
