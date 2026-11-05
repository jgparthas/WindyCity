"""Demo: run the README demo cases through Rule Gate -> agent -> review queue.

Run from the agent/ folder:  python main.py
Needs an API key and product_data/unit_economics.csv. For the full 64-case
run or a gate-only run use ../pipeline.py.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import run_pipeline  # noqa: E402

DEMO_CASES = {
    "TC-02",  # restock
    "TC-05",  # refurbish with data-wipe constraint
    "TC-09",  # donate
    "TC-12",  # recycle
    "TC-19",  # swollen battery: stopped by the gate, agent not called
    "TC-32",  # prompt-injection notes
}


async def main():
    queue = await run_pipeline(only=DEMO_CASES)
    for entry in queue:
        print(f"\n=== {entry['test_case_id']} / {entry['return_id']} ===")
        print(json.dumps(entry, indent=2))
        if entry["gate"]["gate_status"] != "PASS":
            print("Agent intentionally not called: Rule Gate returned "
                  f"{entry['gate']['gate_status']}.")
        elif entry["agent_error"]:
            print(f"AGENT ERROR: {entry['agent_error']}")
    print(f"\n{len(queue)} entries; every entry needs human review.")


if __name__ == "__main__":
    asyncio.run(main())
