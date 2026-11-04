"""End-to-end workflow: return record -> Rule Gate -> agent -> review queue.

    python pipeline.py                         # all 32 synthetic returns
    python pipeline.py --cases TC-02,TC-05     # selected test cases
    python pipeline.py --gate-only             # gate stage only; no API key
    python pipeline.py --out tempHTML/queue.json   # default; the dashboard reads this

HAZARD and INCOMPLETE results skip the agent and go straight to the review
queue. A person approves every entry; nothing here routes an item.

Queue entry = {return_id, test_case_id, needs_human_review, record, gate,
recommendation, agent_error}. `record` is the gate's echoed return record, so
the dashboard needs nothing besides this file. See docs/CONTRACT.md section 4.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT / "agent") not in sys.path:
    sys.path.insert(0, str(ROOT / "agent"))

import data_loader as dl  # noqa: E402  (also makes rule_gate importable)
import rule_gate  # noqa: E402
from models import GateResult  # noqa: E402


def run_gate(records=None, evaluated_at=None) -> list[dict]:
    """Evaluate records (default: product_data/returns.json) in file order."""
    records = records if records is not None else dl.returns()
    return rule_gate.evaluate_batch(
        records, dl.catalog(), dl.recalled(), evaluated_at)


def _summary(result: dict) -> dict:
    return {
        "gate_status": result["gate_status"],
        "route": result["route"],
        "proposed_destination": result["proposed_destination"],
        "reasons": result["reasons"],
        "constraints": result["constraints"],
        "rule_version": result["rule_version"],
    }


async def run_pipeline(
    records=None, only=None, gate_only=False, recommend=None
) -> list[dict]:
    """Return one review-queue entry per record.

    only:      optional set of test_case_ids to run.
    recommend: async callable(GateResult) -> AgentRecommendation; defaults to
               agent.recommend (Claude SDK), imported lazily.
    """
    # The gate always sees the full file order so R08 duplicates behave as in
    # the answer key; the --cases selection is applied afterwards.
    results = run_gate(records)
    if only:
        results = [r for r in results
                   if r["record"].get("test_case_id") in only]

    if not gate_only and recommend is None:
        from agent import recommend  # lazy: needs claude_agent_sdk

    queue = []
    for res in results:
        entry = {
            "return_id": res["return_id"],
            "test_case_id": res["record"].get("test_case_id"),
            "needs_human_review": True,
            "record": res["record"],
            "gate": _summary(res),
            "recommendation": None,
            "agent_error": None,
        }
        if res["gate_status"] == "PASS" and not gate_only:
            try:
                rec = await recommend(GateResult.model_validate(res))
                entry["recommendation"] = rec.model_dump()
            except Exception as error:  # surface to a human, don't crash
                entry["agent_error"] = f"{type(error).__name__}: {error}"
        queue.append(entry)
    return queue


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cases", help="comma-separated test_case_ids")
    ap.add_argument("--gate-only", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "tempHTML" / "queue.json"),
                    help="default: the dashboard's queue.json")
    args = ap.parse_args(argv)

    only = set(args.cases.split(",")) if args.cases else None
    queue = asyncio.run(run_pipeline(only=only, gate_only=args.gate_only))
    Path(args.out).write_text(json.dumps(queue, indent=2), encoding="utf-8")

    counts = {}
    for e in queue:
        counts[e["gate"]["gate_status"]] = \
            counts.get(e["gate"]["gate_status"], 0) + 1
    print(f"Wrote {len(queue)} entries to {args.out}  gate: {counts}")
    errors = [e for e in queue if e["agent_error"]]
    for e in errors:
        print(f"  agent error {e['test_case_id']}: {e['agent_error']}")


if __name__ == "__main__":
    main()
