# Rule Gate

The Rule Gate is a deterministic checkpoint that every return record passes through **before** the sustainability agent sees it. It applies fixed rules (no AI) and decides one of three outcomes:

| gate_status | Meaning | route | proposed_destination |
|---|---|---|---|
| `PASS` | Safe and complete; send to the agent | `agent` | `null` |
| `HAZARD` | Safety or recall rule fired; a human must look | `review_queue` | `human_review` |
| `INCOMPLETE` | Data is missing or wrong; a human must look | `review_queue` | `human_review` |

If rules from several categories fire, precedence is **HAZARD > INCOMPLETE > PASS**.

## Files

| File | Purpose |
|---|---|
| `rule_gate.py` | The gate: loaders plus `evaluate` and `evaluate_batch` |
| `test_rule_gate.py` | Automated tests |
| `rules_v1.md` | Rule reference, keyword list, conventions, open items |
| `../product_data/` | Synthetic data: catalog, recalls, returns, answer key (`eval_labels.csv`) |

Requires Python 3.8+ and nothing else (standard library only).

## How to test it

Run everything from this folder (`rule_gate/`):

```
python -m unittest test_rule_gate -v
```

Expected: `Ran 14 tests ... OK`. The tests cover:
1. **Consistency table**: PASS goes to `agent` with no BLOCK reason; HAZARD and INCOMPLETE go to `review_queue`/`human_review` with at least one BLOCK reason.
2. **Answer key**: all 32 cases in `eval_labels.csv` get the expected status and rule IDs.
3. **Individual rules**: missing fields (R01), same-day purchase (R09), each hazard flag, keyword word boundaries, prompt-injection text, wipe handling (R06), and so on.

To eyeball real output, run the gate on the whole dataset:

```
python rule_gate.py
```

This prints the 32 gate results as JSON. Pass a different data folder as the first argument if you have one.

To try one record yourself:

```python
import rule_gate as g
catalog = g.load_catalog("../product_data/product_catalog.csv")
recalled = g.load_recalled("../product_data/recalled_skus.csv")
record = g.load_returns("../product_data/returns.json")[4]   # TC-05
result = g.evaluate(record, catalog, recalled)
print(result["gate_status"], [r["rule_id"] for r in result["reasons"]])
# PASS ['R06']
```

If a test fails, the `subTest` name in the output is the test-case ID (for example `TC-19`). Compare that case's row in `eval_labels.csv` with the gate output.

## How it works

For each record, `evaluate` runs these checks and collects reasons:

| ID | Check | Severity | Result |
|---|---|---|---|
| R01 | Required field missing or bad date | BLOCK | INCOMPLETE |
| R02 | SKU not in `product_catalog.csv` | BLOCK | INCOMPLETE |
| R03 | SKU in `recalled_skus.csv` | BLOCK | HAZARD |
| R04 | Blocking hazard flag (swollen_battery, overheating_or_burn_marks, leaking_fluid, mold_or_odor, other_hazard) | BLOCK | HAZARD |
| R05 | Hazard keyword in `customer_notes` | BLOCK | HAZARD |
| R06 | Catalog says the product has data storage and `data_wipe_confirmed` is not true | CONSTRAIN | PASS + `data_wipe_required: true` |
| R07 | `condition_grade` missing | WARN | PASS |
| R08 | Duplicate `return_id` (first copy passes, later copies flagged) | BLOCK | INCOMPLETE |
| R09 | `purchase_date` after `received_at` | BLOCK | INCOMPLETE |
| R10 | Record category disagrees with catalog (catalog wins) | WARN | PASS |
| R11 | Non-blocking hazard flag (liquid_damage, cracked_glass_or_casing) | WARN | PASS |

Severities: **BLOCK** stops the record from reaching the agent. **CONSTRAIN** passes with a restriction the agent must respect. **WARN** passes with a note. WARN and CONSTRAIN reasons are only attached to PASS results.

Details such as the keyword list and the full assumptions are in [rules_v1.md](rules_v1.md).

## Output shape

```json
{
  "return_id": "RET-2005",
  "gate_status": "PASS",
  "route": "agent",
  "proposed_destination": null,
  "reasons": [
    {"rule_id": "R06", "severity": "CONSTRAIN",
     "message": "Product has data storage and wipe is not confirmed; wipe required before any resale or donation"}
  ],
  "constraints": {
    "allowed_destinations": ["restock", "refurbish", "donate", "recycle"],
    "data_wipe_required": true
  },
  "record": { "...original record, unchanged..." },
  "rule_version": "v1",
  "evaluated_at": "2026-11-04T09:15:01"
}
```

- `allowed_destinations` is non-empty for PASS and `[]` for HAZARD and INCOMPLETE. For PASS, `donate` is removed if the catalog says the item is not donation eligible, and `recycle` if it is not recyclable.
- `data_wipe_required: true` does not remove any destination. It means a wipe must happen before restock, resale, donation, or release after refurbishment.

## Conventions to know

- **Timestamps** are local receiving-site time with no timezone suffix. If you add timezones, use UTC with a `Z` suffix everywhere.
- **Enums** in the output are lowercase.
- **Duplicates**: `RET-2001` appears twice on purpose. Use `test_case_id` (not `return_id`) when joining test data, and run records through `evaluate_batch` (or share one `seen_ids` set) so R08 can see earlier records.
- **Customer notes are untrusted text.** The gate only pattern-matches them against the keyword list. Nothing in the notes is ever followed as an instruction.
- **Catalog is the source of truth** for category and data storage.

## Connection to the agent

The gate's output object is the agent's input (`GateResult` in `agent/models.py`), with no translation layer. Both read the same `product_data/` files. `pipeline.py` in the repo root runs the full flow, and `agent/tests/test_contract.py` fails if the gate, the data and the agent disagree on a field name or enum. Field dictionary: [../docs/CONTRACT.md](../docs/CONTRACT.md).

## Changing a rule

1. Edit `rule_gate.py` (rule, keyword list, or severity).
2. Bump `RULE_VERSION` in `rule_gate.py`.
3. Update `rules_v1.md` (or add a new version doc), `product_data/eval_labels.csv`, and `test_rule_gate.py` together.
4. Re-run the tests. If you renumber a rule ID, change it in all of the above at once.

## Known open items

- `product_data/unit_economics.csv` is synthetic and was generated to match the answer key; the agent needs it, the gate does not.
- `recalled_skus.csv` contains only one SKU (GAD-1017).
- `has_battery` is in the catalog but no v1 rule uses it.
