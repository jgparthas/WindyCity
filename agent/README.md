# Cosmic Mart Returns Disposition Agent

The agent half of the Cosmic Mart returns workflow. It takes one Rule Gate result for a `PASS` return, gathers facts with read-only tools, and gives the Review Queue a recommendation. A person approves every recommendation. Data is synthetic.

```
Return record -> Rule Gate -> Disposition Agent -> Review Queue -> Human decision
```

The field dictionary shared by the gate, the data and the agent is [../docs/CONTRACT.md](../docs/CONTRACT.md). The agent reads `product_data/` directly, the same files the gate uses.

## Input: Rule Gate result

The agent consumes the gate's output object unchanged (`GateResult` in `models.py`). See CONTRACT.md section 2 for fields. Key points:

- `gate_status` must be `PASS`; HAZARD and INCOMPLETE records never reach the agent.
- Allowed routes come from `constraints.allowed_destinations`.
- `constraints.data_wipe_required` means a wipe must precede restock, resale, donation, or release after refurbishment.
- `record.customer_notes` is untrusted text. The agent treats it as evidence only.
- `record.condition_grade` can be null (WARN R07); the agent infers a condition from the notes or recommends `human_review`.

## Tools (read-only, backed by `product_data/`)

| Tool | Arguments |
|---|---|
| `get_product_info` | sku |
| `get_resale_value` | return_id |
| `get_refurb_cost` | return_id |
| `get_inventory_demand` | return_id |
| `get_donation_partners` | category, condition_grade |
| `get_recycling_rules` | category |
| `get_carbon_estimate` | sku, destination |

`get_resale_value`, `get_refurb_cost` and `get_inventory_demand` need `product_data/unit_economics.csv`. The file in the repo is synthetic, generated to match the answer key; replace it when the data lead supplies the real one. If the file is missing these tools return an error and the agent recommends `human_review` instead of inventing values.

## Output: AgentRecommendation

Fields are listed in CONTRACT.md section 3. `recommended_destination` is one of the gate's allowed destinations or `human_review`. After the model answers, `guard.py` rejects any destination the gate did not allow, carries `data_wipe_required` through to `flags`, and adds `human_review_required` when a person must decide.

## Decision rules

The system prompt in `agent.py` encodes the eight prototype labeling rules from `product_data/README.md` (restock, refurbish thresholds, donation, human review, recycle fallback). They are prototype rules, not confirmed Cosmic Mart policy.

## Run

From PowerShell in the repo root (PowerShell example):

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
pip install -r agent\requirements.txt
cd agent
pytest -q            # offline contract tests; live tests skip without an API key
python main.py       # 6 demo cases through gate -> agent (API key + unit_economics.csv)
cd ..
python pipeline.py --gate-only    # gate stage only, no API key
python pipeline.py                # all 32 returns -> review_queue.json
```

## Files

```text
agent.py          Claude agent: system prompt, MCP tool server, recommend()
guard.py          Post-checks on the agent's output (no SDK needed)
claude_tools.py   MCP wrappers for the tools
tools.py          Tool functions reading product_data via data_loader
data_loader.py    Loads product_data/ and rule_gate loaders in one place
models.py         GateResult, ReturnRecord, AgentRecommendation schemas
main.py           Demo cases
tests/            test_contract.py (offline), test_project.py (tools, live)
../pipeline.py    End-to-end gate -> agent -> review queue
```

## Assumptions

All prices, demand levels, carbon factors and thresholds are synthetic. Carbon values are placeholders until the team agrees on a methodology. The earlier hand-written `mock_data.py` and the offline `local_agent.py` were removed so there is a single data source and one agent.
