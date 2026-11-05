"""End-to-end test: Rule Gate -> agent -> webpage.

Runs the whole system and records what each stage produced:

    tests/output/rules_gate_output.txt   stage 1, every return the gate saw
    tests/output/agent_output.txt        stage 2 (+ a stage 3 webpage section)

    cd WindyCity
    pytest tests/test_full_system.py -v

Environment:
    The live Claude agent runs when claude_agent_sdk is installed and either
    ANTHROPIC_API_KEY is set or the `claude` CLI is on PATH (logged in).
    Otherwise a stub recommender is used and the output file says so.
    E2E_STUB=1        force the stub (fast, offline).
    E2E_CASES         comma-separated test_case_ids for the agent stage
                      (default: all 64 returns).

In live mode the agent's queue is written to tempHTML/queue.json, which is
the webpage's input, and the webpage stage serves tempHTML/ itself. In stub
mode a temporary copy is served so placeholder data never lands there.
"""
from __future__ import annotations

import asyncio
import functools
import http.server
import importlib.util
import json
import os
import shutil
import sys
import threading
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = Path(__file__).resolve().parent / "output"
for p in (ROOT, ROOT / "agent"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pipeline  # noqa: E402
from models import AgentRecommendation, OptionAssessment  # noqa: E402

GATE_STATUSES = {"PASS", "HAZARD", "INCOMPLETE"}
OUTCOMES = {"restock", "refurbish", "donate", "recycle", "waste", "human_review"}
LIVE = (
    not os.environ.get("E2E_STUB")
    and importlib.util.find_spec("claude_agent_sdk") is not None
    and bool(os.environ.get("ANTHROPIC_API_KEY") or shutil.which("claude"))
)


def _selected_cases():
    raw = os.environ.get("E2E_CASES", "").strip()
    if not raw or raw.lower() == "all":
        return None
    return set(raw.split(","))


async def _stub_recommend(gate_result):
    """Offline stand-in for agent.recommend: first allowed destination."""
    dest = gate_result.allowed_destinations[0]
    return AgentRecommendation(
        return_id=gate_result.return_id,
        test_case_id=gate_result.record.test_case_id,
        recommended_destination=dest,
        needs_review=True,
        expected_recovery_usd=0.0,
        estimated_carbon_emission_avoided_kg=0.0,
        confidence=0.5,
        value_at_stake_usd=gate_result.record.original_price,
        flags=["stub"],
        evidence=["STUB: no model was called"],
        alternatives=[OptionAssessment(
            destination=dest, eligible=True, expected_recovery_usd=0.0,
            carbon_avoided_kg=0.0, rationale="stub")],
        justification="STUB recommendation: first destination the gate allows.",
    )


# ---------- report writers ----------

def _write_gate_report(results, path):
    counts = Counter(r["gate_status"] for r in results)
    lines = [
        "RULES GATE OUTPUT (stage 1)",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"Rule version: {results[0]['rule_version']}",
        f"Returns evaluated: {len(results)}",
        "Summary: " + ", ".join(f"{k}={counts.get(k, 0)}"
                                for k in sorted(GATE_STATUSES)),
        "=" * 78,
    ]
    for r in results:
        rec = r["record"]
        lines += [
            "",
            f"{rec.get('test_case_id')}  {r['return_id']}  "
            f"{rec.get('product_name')} ({rec.get('sku')})",
            f"  gate_status          : {r['gate_status']}",
            f"  route                : {r['route']}",
            f"  proposed_destination : {r['proposed_destination']}",
            f"  allowed_destinations : {r['constraints']['allowed_destinations']}",
            f"  data_wipe_required   : {r['constraints']['data_wipe_required']}",
            "  reasons:" + ("" if r["reasons"] else " none"),
        ]
        lines += [f"    [{x['rule_id']}] {x['severity']}: {x['message']}"
                  for x in r["reasons"]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_agent_report(queue, path, mode, selected, web):
    lines = [
        "AGENT OUTPUT (stage 2)",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"Mode: {mode}",
        "Cases: " + ("all" if selected is None else ", ".join(sorted(selected))),
        f"Queue entries: {len(queue)}",
        "=" * 78,
    ]
    for e in queue:
        g, a = e["gate"], e["recommendation"]
        lines += ["", f"{e['test_case_id']}  {e['return_id']}  "
                      f"gate={g['gate_status']}"]
        if e["agent_error"]:
            lines.append(f"  AGENT ERROR: {e['agent_error']}")
        elif a is None:
            lines.append("  skipped by the gate; sent straight to human review "
                         f"({g['proposed_destination']})")
        else:
            lines += [
                f"  recommended_destination : {a['recommended_destination']}",
                f"  needs_review            : {a['needs_review']}",
                f"  expected_recovery_usd   : {a['expected_recovery_usd']}",
                f"  carbon_avoided_kg       : "
                f"{a['estimated_carbon_emission_avoided_kg']}",
                f"  confidence              : {a['confidence']}",
                f"  value_at_stake_usd      : {a['value_at_stake_usd']}",
                f"  flags                   : {a['flags']}",
                "  evidence:",
                *[f"    - {x}" for x in a["evidence"]],
                "  alternatives:",
                *[f"    - {x['destination']}: eligible={x['eligible']} "
                  f"recovery={x['expected_recovery_usd']} "
                  f"carbon={x['carbon_avoided_kg']} ({x['rationale']})"
                  for x in a["alternatives"]],
                f"  justification: {a['justification']}",
            ]
    lines += ["", "=" * 78, "WEBPAGE (stage 3)",
              f"Served {web['site']} at {web['base']}",
              f"  index.html  -> HTTP {web['index_status']}",
              f"  queue.json  -> HTTP {web['queue_status']}, "
              f"{web['entries']} entries, all renderable by script.js normalize()"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------- stage 3 ----------

def _serve_and_fetch(queue, tmp_dir):
    if LIVE:  # agent output is the webpage's real input
        site, label = ROOT / "tempHTML", "tempHTML/ (queue.json written from this run)"
    else:     # keep stub data out of the real queue.json
        site, label = tmp_dir / "site", "a temp copy of tempHTML/ (stub queue)"
        shutil.copytree(ROOT / "tempHTML", site)
    (site / "queue.json").write_text(json.dumps(queue, indent=2),
                                     encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(site))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(base + "/index.html") as r:
            index_status, index_html = r.status, r.read().decode("utf-8")
        with urllib.request.urlopen(base + "/queue.json") as r:
            queue_status, served = r.status, json.loads(r.read())
    finally:
        server.shutdown()
        server.server_close()
    return {"site": label, "base": base, "index_status": index_status,
            "index_html": index_html, "queue_status": queue_status,
            "served": served, "entries": len(served)}


# ---------- the run ----------

@pytest.fixture(scope="module")
def system(tmp_path_factory):
    OUT_DIR.mkdir(exist_ok=True)
    selected = _selected_cases()

    gate_results = pipeline.run_gate()
    _write_gate_report(gate_results, OUT_DIR / "rules_gate_output.txt")

    queue = asyncio.run(pipeline.run_pipeline(
        only=selected, recommend=None if LIVE else _stub_recommend))

    web = _serve_and_fetch(queue, tmp_path_factory.mktemp("web"))

    mode = ("LIVE (Claude Agent SDK)" if LIVE else
            "STUB - ANTHROPIC_API_KEY not set; recommendations below were "
            "NOT produced by a model")
    _write_agent_report(queue, OUT_DIR / "agent_output.txt", mode, selected, web)
    return {"gate": gate_results, "queue": queue, "web": web}


# ---------- assertions ----------

def test_stage1_rules_gate(system):
    results = system["gate"]
    assert len(results) == 64
    assert {r["gate_status"] for r in results} <= GATE_STATUSES
    assert (OUT_DIR / "rules_gate_output.txt").stat().st_size > 0


def test_stage2_agent(system):
    assert system["queue"]
    if LIVE:
        passed = [e for e in system["queue"]
                  if e["gate"]["gate_status"] == "PASS"]
        assert any(not e["agent_error"] for e in passed), (
            "every live agent call failed; check auth. First error: "
            f"{passed[0]['agent_error'] if passed else None}")
    for e in system["queue"]:
        a, g = e["recommendation"], e["gate"]
        if g["gate_status"] != "PASS":
            assert a is None, f"{e['test_case_id']}: gate-stopped item reached agent"
            continue
        if e["agent_error"]:
            continue  # recorded in agent_output.txt for a human to see
        assert a["recommended_destination"] in OUTCOMES
        assert (a["recommended_destination"] == "human_review"
                or a["recommended_destination"]
                in g["constraints"]["allowed_destinations"]), e["test_case_id"]
    assert (OUT_DIR / "agent_output.txt").stat().st_size > 0


def test_stage3_webpage(system):
    web = system["web"]
    assert web["index_status"] == 200 and web["queue_status"] == 200
    assert "script.js" in web["index_html"]
    assert web["served"] == system["queue"]
    # Fields script.js normalize() dereferences for every entry.
    for e in web["served"]:
        assert e["record"]["sku"] and e["record"]["product_name"]
        assert e["gate"]["gate_status"] in GATE_STATUSES
        assert "allowed_destinations" in e["gate"]["constraints"]
        a = e["recommendation"]
        if a:
            assert isinstance(a["flags"], list)
            assert isinstance(a["alternatives"], list)
