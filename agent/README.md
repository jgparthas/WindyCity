# Cosmic Mart Returns Disposition Agent

This project demonstrates the agent and read-tool portion of the Cosmic Mart returns workflow. It runs locally, requires no API key, and uses synthetic data.

## Workflow

```text
Return record
    -> Rule Gate
    -> Disposition Agent
    -> Review Queue
    -> Human decision
```

The Rule Gate handles deterministic safety and data-quality checks. The agent evaluates only returns with a `PASS` status. The agent recommends a destination but does not authorize or execute the route.

## Rule Gate to Agent

The Rule Gate gives the agent one `GateResult` JSON object containing:

- the gate status;
- the destinations the agent is allowed to consider;
- constraints that must remain attached to the recommendation;
- reasons supplied by the Rule Gate;
- the validated return record.

Items with `HAZARD` or `INCOMPLETE` status do not enter the agent. The demo sends those items directly to human review.

### Input JSON fields

#### Gate result

| Field | Type | Description |
|---|---|---|
| `status` | string | Rule Gate result: `PASS`, `HAZARD`, or `INCOMPLETE`. |
| `allowed_destinations` | array of strings | Routes the agent may consider: `restock`, `refurbish`, `resell`, `donate`, and `recycle`. |
| `constraints` | array of strings | Mandatory conditions such as `data_wipe_required`. |
| `reasons` | array of strings | Rule Gate findings such as `swollen_battery`. |
| `record` | object | Validated return information. |

#### Return record

| Field | Type | Description |
|---|---|---|
| `return_id` | string | Unique return identifier. |
| `sku` | string | Product stock-keeping unit. |
| `category` | string | `gadgets`, `apparel`, or `home`. |
| `product_name` | string | Display name of the returned item. |
| `original_price_usd` | number | Original sale price in US dollars. |
| `customer_notes` | string | Untrusted customer-provided description of the item. |
| `condition_grade` | string or null | Warehouse condition grade: `A`, `B`, `C`, or `D`. |

### Example agent input

```json
{
  "status": "PASS",
  "allowed_destinations": [
    "restock",
    "refurbish",
    "resell",
    "donate",
    "recycle"
  ],
  "constraints": [
    "data_wipe_required"
  ],
  "reasons": [],
  "record": {
    "return_id": "RET-002",
    "sku": "GAD-1002",
    "category": "gadgets",
    "product_name": "Smartwatch",
    "original_price_usd": 129.0,
    "customer_notes": "Screen flickers sometimes and box is gone.",
    "condition_grade": "C"
  }
}
```

## Agent tools

The agent uses read-only tools to gather the facts needed for a recommendation:

- `get_product_info`
- `get_resale_value`
- `get_refurb_cost`
- `get_inventory_demand`
- `get_donation_partners`
- `get_recycling_rules`
- `get_carbon_estimate`

Tool calls and results are printed during the demo for traceability.

## Agent to Review Queue

For each eligible return, the agent gives the Review Queue one `AgentRecommendation` JSON object. The object contains the recommendation, expected recovery, carbon estimate, confidence, review flags, supporting evidence, all assessed alternatives, and a concise justification.

The Review Queue receives a recommendation only. A person must approve, modify, or reject it before any routing action occurs.

### Output JSON fields

#### Agent recommendation

| Field | Type | Description |
|---|---|---|
| `return_id` | string | Return associated with the recommendation. |
| `recommended_destination` | string | Proposed route: `restock`, `refurbish`, `resell`, `donate`, or `recycle`. |
| `expected_recovery_usd` | number | Estimated recovery for the proposed route. |
| `estimated_carbon_emission_avoided_kg` | number | Estimated carbon avoided compared with the demo baseline. |
| `confidence` | number | Confidence from `0.0` to `1.0`. |
| `value_at_stake_usd` | number | Difference between the leading and next-best modeled scores. |
| `flags` | array of strings | Constraints and conditions that require reviewer attention. |
| `evidence` | array of strings | Facts used to support the recommendation. |
| `alternatives` | array of objects | Side-by-side assessments of all five destinations. |
| `justification` | string | Concise explanation for the reviewer. |

#### Alternative assessment

| Field | Type | Description |
|---|---|---|
| `destination` | string | Destination being assessed. |
| `eligible` | boolean | Whether the destination is permitted and meets demo policy. |
| `expected_recovery_usd` | number | Estimated recovery if eligible; otherwise `0`. |
| `carbon_avoided_kg` | number | Estimated carbon avoided for the destination. |
| `rationale` | string | Eligibility or policy explanation. |

### Example Review Queue payload

```json
{
  "return_id": "RET-002",
  "recommended_destination": "refurbish",
  "expected_recovery_usd": 61.5,
  "estimated_carbon_emission_avoided_kg": 14.0,
  "confidence": 0.75,
  "value_at_stake_usd": 3.6,
  "flags": [
    "data_wipe_required",
    "close_tradeoff_review"
  ],
  "evidence": [
    "Condition grade: C",
    "Market value: $82.50",
    "Refurbishment cost: $21.00",
    "Demand: HIGH with 14 units on hand"
  ],
  "alternatives": [
    {
      "destination": "refurbish",
      "eligible": true,
      "expected_recovery_usd": 61.5,
      "carbon_avoided_kg": 14.0,
      "rationale": "Requires a repairable B/C item and repair cost below 45% of market value."
    }
  ],
  "justification": "Recommend refurbish: modeled recovery is $61.50, demand is HIGH, and estimated carbon avoided is 14.0 kg. Human approval is required."
}
```

The example shortens the `alternatives` array for readability. The running application includes all five destination assessments.

## Demo cases

- `RET-001`: restock
- `RET-002`: refurbish
- `RET-003`: resell
- `RET-004`: donate
- `RET-005`: recycle
- `RET-006`: hazard escalation; the agent is not called

## Run the project

From PowerShell in the project folder:

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pytest -q
python main.py
```

## Project files

```text
agent.py       Recommendation logic and option comparison
main.py        Demo cases and batch summary
mock_data.py   Synthetic data used by the read tools
models.py      Input and output schemas
tools.py       Read-only tool functions
tests/         Automated tests
```

## Assumptions

All prices, demand levels, partner distances, carbon values, scoring weights, and eligibility thresholds are synthetic. The local controller demonstrates the interfaces, tool flow, traceability, safety boundary, and review payload. It is not an LLM implementation.
