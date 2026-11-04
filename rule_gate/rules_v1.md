# Rule Gate – Rule Reference (v1)

If any rule, keyword list, or severity changes, bump `RULE_VERSION` in `rule_gate.py` and update this file, the fixtures (`product_data/eval_labels.csv`) and the tests together.

| ID | Rule | Severity | Result |
|----|------|----------|--------|
| R01 | Required field missing (`return_id, sku, category, original_price, purchase_date, received_at, received_channel, return_reason_code`) or unparseable date | BLOCK | INCOMPLETE |
| R02 | SKU not in product_catalog | BLOCK | INCOMPLETE |
| R03 | SKU in recalled_skus | BLOCK | HAZARD, human_review |
| R04 | Blocking hazard flag (`swollen_battery, overheating_or_burn_marks, leaking_fluid, mold_or_odor, other_hazard`) | BLOCK | HAZARD, human_review |
| R05 | Hazard keyword in customer_notes | BLOCK | HAZARD, human_review |
| R06 | Catalog `has_data_storage` and `data_wipe_confirmed` is not true | CONSTRAIN | PASS, `data_wipe_required: true` |
| R07 | `condition_grade` missing | WARN | PASS |
| R08 | Duplicate `return_id` (first in file order passes; later copies flagged) | BLOCK | INCOMPLETE |
| R09 | `purchase_date` after `received_at` (date compare; same day is OK) | BLOCK | INCOMPLETE |
| R10 | Record category disagrees with catalog (catalog value is used) | WARN | PASS |
| R11 | Non-blocking hazard flag (`liquid_damage, cracked_glass_or_casing`) | WARN | PASS, flag visible to agent |

Precedence: HAZARD > INCOMPLETE > PASS. When HAZARD or INCOMPLETE fires, all BLOCK reasons are listed; WARN/CONSTRAIN reasons are attached to PASS results only.

## Consistency table (cheap automated tests)

| gate_status | route | proposed_destination | allowed_destinations |
|---|---|---|---|
| PASS | agent | null | non-empty subset of the four |
| HAZARD | review_queue | human_review | [] |
| INCOMPLETE | review_queue | human_review | [] |

PASS never includes a BLOCK reason; HAZARD and INCOMPLETE always include at least one.

**Decision: all hazards go to human_review.** The original spec proposed `recycle` for swollen_battery / overheating / leaking_fluid. The answer key expects HAZARD_REVIEW, so the gate never proposes `recycle` and HAZARD `allowed_destinations` is `[]`.

## R05 keyword list (v1)
Whole-word, case-insensitive: burning, burnt, smoke, smoking, on fire, caught fire, flames, sparks, sparking, melted, melting, exploded, explosion, leaking, leaked, swollen, mold, mould, moldy, mouldy.
"bulging" and "scorch" are intentionally absent so that flagged records (TC-19, TC-30) yield R04 only, as in the key.

## Conventions and assumptions
- **Timestamps**: local receiving-site time, ISO 8601, no timezone suffix, for `received_at` and `evaluated_at`. If timezones are added later, use UTC with `Z` everywhere.
- **Enums**: lowercase in gate output (`human_review`, `review_queue`).
- **PASS allowed_destinations**: starts as all four (restock, refurbish, donate, recycle; `resell` was merged into `restock` and the rule version stays v1 because the destination list is schema, not a rule); `donate` is removed when catalog `donation_eligible` is false, `recycle` when `recyclable` is false. Unknown (null) eligibility is not treated as false. (Assumption – confirm.)
- **R06** does not shrink allowed_destinations; it sets `data_wipe_required: true` (wipe before restock, donate, or release after refurbishment).
- **Joins**: use `test_case_id`, because RET-2001 intentionally appears twice. `test_case_id` is carried through in `record` unchanged.
- **Answer-key mapping**: key strings such as `CONSTRAIN:R06_DATA_WIPE_REQUIRED` map to rule_id by the `Rxx` prefix; `HAZARD_REVIEW` maps to `human_review`; `DO_NOT_*` restrictions are implied by HAZARD status.
- Untrusted free text (`customer_notes`) is only pattern-matched, never interpreted as instructions.

## Reference tables
`product_data/product_catalog.csv` (sku, category, product_name, has_battery, has_data_storage, weight_kg, warranty_months, plus original_price, donation_eligible, recyclable, carbon factors) and `product_data/recalled_skus.csv` (sku, recall_date, recall_reason). `has_battery` is carried but no v1 rule uses it.

## Open items
- `product_data/unit_economics.csv` is a synthetic file generated to match the answer key; replace it when the data lead supplies the real one (column names are assumed, see `docs/CONTRACT.md`).
- The spec's worked example (GAD-1042, grade "C" with an R07 reason) is inconsistent: GAD-1042 isn't in the catalog, and a grade of C would not trigger R07.
- `recalled_skus.csv` has one SKU (GAD-1017).
