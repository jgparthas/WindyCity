"""Score a review_queue.json (from pipeline.py) against product_data/eval_labels.csv.

    python evaluate_queue.py [queue.json]  (default: tempHTML/queue.json)

A PASS case counts as matching when the agent's destination equals the key, OR
the key says HUMAN_REVIEW and the agent sent the item to a person
(needs_review is true). Sending an uncertain item to a person is correct.
Gate-stopped cases are matched on gate_status only; the agent is not called.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
queue_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "tempHTML" / "queue.json"
queue = json.loads(queue_path.read_text(encoding="utf-8"))
with open(ROOT / "product_data" / "eval_labels.csv", newline="", encoding="utf-8") as f:
    labels = {r["test_case_id"]: r for r in csv.DictReader(f)}

gate_ok = agent_ok = agent_n = 0
rows = []
for e in queue:
    tc = e["test_case_id"]
    lab = labels[tc]
    g = e["gate"]["gate_status"]
    gate_ok += g == lab["expected_gate_status"]
    rec = e["recommendation"]
    if rec is None:
        note = "agent skipped (gate stop)" if g != "PASS" else \
            f"AGENT ERROR {e['agent_error']}"
        rows.append((tc, g, "-", lab["expected_destination"], note))
        continue
    agent_n += 1
    dest = rec["recommended_destination"].upper()
    key = lab["expected_destination"]
    ok = dest == key or (key == "HUMAN_REVIEW" and rec["needs_review"])
    agent_ok += ok
    how = "OK" if dest == key else ("OK (sent to a person)" if ok else "DIFF")
    rows.append((tc, g, f"{dest} review={rec['needs_review']}", key, how))

print(f"{'TC':6}{'gate':12}{'agent':30}{'key':15}result")
for r in rows:
    print(f"{r[0]:6}{r[1]:12}{r[2]:30}{r[3]:15}{r[4]}")
print(f"\nentries={len(queue)}  gate matches key={gate_ok}/{len(queue)}  "
      f"agent matches key={agent_ok}/{agent_n}")
print("every entry needs human review:",
      all(e["needs_human_review"] for e in queue))
sys.exit(0 if gate_ok == len(queue) and agent_ok == agent_n else 1)
