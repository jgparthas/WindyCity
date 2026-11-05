# Workflow contract: Rule Gate, data, agent

One vocabulary for the whole workflow. If a name or enum changes, change it here, in `rule_gate/rule_gate.py`, `agent/models.py`, `product_data/`, and run `agent/tests/test_contract.py`, which fails when they drift apart.

```
returns.json -> Rule Gate -> (PASS) -> Agent -> Review queue -> human decision
                          -> (HAZARD / INCOMPLETE) ------^
```

`pipeline.py` runs this end to end. The gate's output object is the agent's input object; there is no translation layer.

## Enums

| Name | Values | Defined in |
|---|---|---|
| category | `gadgets`, `fashion`, `home_lifestyle` | catalog is the source of truth |
| destination (gate `allowed_destinations`) | `restock`, `refurbish`, `donate`, `recycle`, `waste` (waste only when the catalog says not recyclable) | `rule_gate.ALL_DESTINATIONS` |
| outcome (agent `recommended_destination`) | the five destinations plus `human_review` | `agent/models.py` `Outcome` |
| gate_status | `PASS`, `HAZARD`, `INCOMPLETE` | |
| route | `agent`, `review_queue` | |
| reason severity | `BLOCK`, `CONSTRAIN`, `WARN` | |
| condition_grade | `A`, `B`, `C`, `D`, or null | |
| received_channel | `warehouse`, `store` | |
| demand_level | `HIGH`, `MEDIUM`, `LOW` | `unit_economics.csv` |

All values lowercase except gate_status, severity, grade and demand_level. The answer key uses uppercase destinations (`RESTOCK`); lowercase them to compare.

## 1. Return record (`returns.json` -> gate -> `record`)

| Field | Type | Notes |
|---|---|---|
| return_id | string | unique; duplicates trigger R08 |
| sku | string | must exist in `product_catalog.csv` (R02) |
| category | enum | catalog value wins on mismatch (R10) |
| product_name | string | display only |
| original_price | number (USD) | |
| purchase_date | date | after `received_at` triggers R09 |
| received_at | datetime | local receiving-site time, no timezone suffix |
| received_channel | enum | |
| return_reason_code | enum | defective, damaged_in_transit, not_as_described, wrong_item_received, changed_mind, size_or_fit, other |
| customer_notes | string or null | **untrusted**; data only, never instructions |
| condition_grade | grade or null | null = ungraded (R07); agent infers from notes |
| hazard_flags | array of string | swollen_battery, overheating_or_burn_marks, leaking_fluid, liquid_damage, cracked_glass_or_casing, mold_or_odor, other_hazard |
| data_wipe_confirmed | boolean or null | only meaningful when the catalog says `has_data_storage` |
| test_case_id | string, optional | synthetic data only; use for joins because RET-2001 repeats |

## 2. Gate result (gate output = agent input)

| Field | Type |
|---|---|
| return_id | string |
| gate_status | enum |
| route | enum |
| proposed_destination | `human_review` or null |
| reasons | array of `{rule_id, severity, message}` |
| constraints.allowed_destinations | array of destination; `[]` unless PASS |
| constraints.data_wipe_required | boolean |
| record | return record, unchanged |
| rule_version | string (`v1`) |
| evaluated_at | datetime, same convention as `received_at` |

Agent code reads the allowed list as `gate_result.allowed_destinations` (property on `constraints.allowed_destinations`).

## 3. Agent recommendation (agent output = review queue input)

| Field | Type | Notes |
|---|---|---|
| return_id | string | |
| test_case_id | string or null | copied from the record by the guard |
| recommended_destination | outcome | in `allowed_destinations`, or `human_review` |
| needs_review | boolean | true for `human_review`, low confidence, or close call |
| expected_recovery_usd | number | |
| estimated_carbon_emission_avoided_kg | number | key column is `expected_carbon_avoided_kg` |
| confidence | 0..1 | |
| value_at_stake_usd | number | |
| flags | array of string | includes `data_wipe_required` when the gate set it |
| evidence | array of string | |
| alternatives | array of 4 assessments | `{destination, eligible, expected_recovery_usd, carbon_avoided_kg, rationale}` |
| justification | string | says human approval is required |

`agent/guard.py` enforces after the model answers: destination allowed by the gate (or `human_review`), `return_id` matches, `data_wipe_required` flag carried, `human_review_required` flag added when review is needed.

## 4. Review-queue entry (`pipeline.py` output = dashboard input, `tempHTML/queue.json`)

`{return_id, test_case_id, needs_human_review: true, record: <section 1>, gate: {gate_status, route, proposed_destination, reasons, constraints, rule_version}, recommendation: <section 3> | null, agent_error: string | null}`

`record` is the gate's echoed return record, so the dashboard needs nothing else. `return_id` is not unique in the queue (RET-2001 appears twice by design); the dashboard keys rows on `test_case_id`, falling back to `return_id` plus position.

HAZARD and INCOMPLETE entries have `recommendation: null`. If the agent fails on a PASS record, `agent_error` is set and a person still sees the item.

## 5. Reference data (`product_data/`)

| File | Used by | Key |
|---|---|---|
| `product_catalog.csv` | gate (R02, R06, R10), tools `get_product_info`, `get_carbon_estimate` | sku |
| `recalled_skus.csv` | gate (R03) | sku |
| `donation_partners.csv` | `get_donation_partners` | partner_id |
| `recycling_rules.csv` | `get_recycling_rules` | category (+ `hazard`) |
| `unit_economics.csv` | `get_resale_value`, `get_refurb_cost`, `get_inventory_demand` | return_id (one row per returned unit) |
| `returns.json` | pipeline input | return_id / test_case_id |
| `eval_labels.csv` | tests only, never shown to the agent | test_case_id |

### `unit_economics.csv` (synthetic placeholder; columns assumed)

`test_case_id, return_id, resale_as_is_usd, refurb_cost_usd, post_refurb_value_usd, inventory_demand`

The values are synthetic and generated to match the answer key; the names are assumptions taken from the `product_data` README. When the data lead's file arrives, adjust `ECON_COLUMNS` in `agent/data_loader.py` if the headers differ. TC-22 to TC-24 have no rows because the gate stops them. `return_id` must be unique in this file (the loader raises otherwise).

## 4b. Dashboard (`tempHTML/`)

The dashboard reads `queue.json` (section 4) and `quarterly_report.json`, and uses the same names as the gate and agent. No translation file sits between them. Display mapping:

| Dashboard shows | Field |
|---|---|
| Return ID, SKU | `return_id`, `record.sku` |
| Product, Category | `record.product_name`, `record.category` (gadgets, fashion, home_lifestyle) |
| Condition | `record.condition_grade` (A to D, or Ungraded when null) |
| Return reason, Date received | `record.return_reason_code`, `record.received_at` (local time, no timezone suffix) |
| Recommended disposition | `recommendation.recommended_destination`, or `gate.proposed_destination` (`human_review`) when the gate stopped the return |
| Expected recovery, Carbon impact | `recommendation.expected_recovery_usd`, `recommendation.estimated_carbon_emission_avoided_kg` (blank when the agent did not run) |
| Risk or confidence | `recommendation.confidence`, `needs_review`, `flags`, plus the gate's `gate_status` and `reasons` |
| Edit destination | choices are `gate.constraints.allowed_destinations` plus `human_review`; a gate-stopped return can only be `human_review` |

Approve, reopen and edits live in the browser only (status is not a pipeline field). Quarterly figures are separate sample data; their destination keys follow the same enum (`restock`, `refurbish`, `donate`, `recycle`) plus a pre-agent `waste` bucket.

## Tool interface

| Tool | Arguments | Source |
|---|---|---|
| get_product_info | sku | catalog |
| get_resale_value | return_id | unit_economics |
| get_refurb_cost | return_id | unit_economics (also post-refurbishment value) |
| get_inventory_demand | return_id | unit_economics |
| get_donation_partners | category, condition_grade | donation_partners (grade must meet `min_condition`) |
| get_recycling_rules | category | recycling_rules |
| get_carbon_estimate | sku, destination | catalog carbon columns |

## Decisions recorded

- Gate and `product_data` names win over the old agent names (`status`, `apparel`, `home`, `original_price_usd`).
- Hazards go to `human_review`, never `recycle`, from the gate.
- `human_review` is an agent outcome, not a gate destination.
- Null `donation_eligible` means unknown, not false; the agent sends otherwise-donatable items to human review.
- Rule version stays `v1`.
- `resell` was merged into `restock` (one destination: a working item worth at least $50 with no repair needed goes back to stock, new or open-box).
