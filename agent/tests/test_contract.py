"""Contract tests: the Rule Gate, product_data and the agent share one
vocabulary. All offline; no API key needed."""
import asyncio
import csv
import re
import typing

import pytest

import data_loader as dl
import rule_gate
from guard import enforce_gate
from models import (
    AgentRecommendation,
    Category,
    Channel,
    Destination,
    GateResult,
    Grade,
    ReasonCode,
)
from pipeline import run_gate, run_pipeline

RESULTS = run_gate(evaluated_at="2026-11-03T00:00:00")
BY_TC = {r["record"]["test_case_id"]: r for r in RESULTS}
with open(dl.DATA_DIR / "eval_labels.csv", newline="", encoding="utf-8") as f:
    LABELS = {r["test_case_id"]: r for r in csv.DictReader(f)}


def literal_set(t):
    return set(typing.get_args(t))


# ----------------------------------------------------------- shared enums
def test_enums_match_across_gate_catalog_and_agent():
    assert literal_set(Category) == rule_gate.CATEGORIES
    assert literal_set(Category) == {r["category"]
                                     for r in dl.catalog().values()}
    assert set(literal_set(Destination)) == set(rule_gate.ALL_DESTINATIONS)
    assert literal_set(Grade) == rule_gate.GRADES
    assert literal_set(Channel) == rule_gate.CHANNELS
    assert literal_set(ReasonCode) == rule_gate.REASON_CODES


def test_every_partner_and_recycling_category_is_a_known_category():
    known = literal_set(Category)
    for p in dl.donation_partners():
        assert set(p["accepts_categories"]) <= known
    assert set(dl.recycling_rules()) == known | {"hazard"}


# ------------------------------------------- gate output feeds the agent
@pytest.mark.parametrize("tc", sorted(BY_TC))
def test_gate_output_validates_as_agent_input(tc):
    res = BY_TC[tc]
    gr = GateResult.model_validate(res)
    assert gr.gate_status == res["gate_status"]
    assert gr.allowed_destinations == res["constraints"]["allowed_destinations"]
    assert gr.record.return_id == res["return_id"]
    # every field the gate echoes in the record is known to the agent model
    assert set(res["record"]) <= set(type(gr.record).model_fields)


def test_pipeline_gate_stage_matches_answer_key():
    queue = asyncio.run(run_pipeline(gate_only=True))
    assert len(queue) == 64
    for entry in queue:
        lab = LABELS[entry["test_case_id"]]
        assert entry["gate"]["gate_status"] == lab["expected_gate_status"]
        got = {r["rule_id"] for r in entry["gate"]["reasons"]}
        assert got == set(re.findall(r"R\d\d", lab["expected_gate_reasons"]))
        assert entry["needs_human_review"] is True
        assert entry["recommendation"] is None


def test_pipeline_calls_agent_only_for_pass():
    seen = []

    async def fake(gate_result):
        seen.append(gate_result.record.test_case_id)
        return AgentRecommendation(
            return_id=gate_result.return_id,
            recommended_destination="human_review",
            expected_recovery_usd=0,
            estimated_carbon_emission_avoided_kg=0,
            confidence=0.5,
            value_at_stake_usd=0,
            justification="Stub recommendation; human approval is required.",
        )

    queue = asyncio.run(run_pipeline(recommend=fake))
    passed = {e["test_case_id"] for e in queue
              if e["gate"]["gate_status"] == "PASS"}
    assert set(seen) == passed
    assert len(passed) == 55
    for e in queue:
        assert (e["recommendation"] is not None) == (
            e["gate"]["gate_status"] == "PASS")


def test_pipeline_survives_agent_errors():
    async def boom(gate_result):
        raise RuntimeError("no api key")

    queue = asyncio.run(run_pipeline(only={"TC-02"}, recommend=boom))
    assert queue[0]["recommendation"] is None
    assert "no api key" in queue[0]["agent_error"]


# ------------------------------------------------------------- the guard
def make_rec(rid, dest, **kw):
    return AgentRecommendation(
        return_id=rid,
        recommended_destination=dest,
        expected_recovery_usd=0,
        estimated_carbon_emission_avoided_kg=0,
        confidence=0.9,
        value_at_stake_usd=0,
        justification="Stub recommendation; human approval is required.",
        **kw,
    )


def test_guard_blocks_destinations_the_gate_did_not_allow():
    gr = GateResult.model_validate(BY_TC["TC-05"])
    gr.constraints.allowed_destinations = ["recycle"]
    with pytest.raises(ValueError):
        enforce_gate(make_rec(gr.return_id, "donate"), gr)


def test_guard_allows_human_review_and_adds_flags():
    gr = GateResult.model_validate(BY_TC["TC-05"])  # data wipe required
    out = enforce_gate(make_rec(gr.return_id, "human_review"), gr)
    assert "data_wipe_required" in out.flags
    assert out.needs_review is True
    assert out.test_case_id == "TC-05"


def test_guard_allows_waste_only_when_the_gate_does():
    gr = GateResult.model_validate(BY_TC["TC-14"])
    assert "waste" in gr.allowed_destinations  # FSH-3003 is not recyclable
    assert "recycle" not in gr.allowed_destinations
    assert enforce_gate(make_rec(gr.return_id, "waste"), gr)
    with pytest.raises(ValueError):
        enforce_gate(make_rec(gr.return_id, "recycle"), gr)
    other = GateResult.model_validate(BY_TC["TC-02"])
    with pytest.raises(ValueError):
        enforce_gate(make_rec(other.return_id, "waste"), other)


def test_guard_rejects_non_pass_and_mismatched_ids():
    hazard = GateResult.model_validate(BY_TC["TC-19"])
    with pytest.raises(ValueError):
        enforce_gate(make_rec(hazard.return_id, "recycle"), hazard)
    ok = GateResult.model_validate(BY_TC["TC-02"])
    with pytest.raises(ValueError):
        enforce_gate(make_rec("RET-OTHER", "restock"), ok)


# ------------------------------------------- shipped unit_economics.csv
def test_shipped_economics_covers_every_gated_record_and_matches_key():
    """Every record that is not stopped before the agent has a row, the three
    gate-stopped TC-22..24 do not, and the numbers reproduce the key's
    expected recovery for refurbish cases (post-refurb value minus cost)."""
    dl.unit_economics.cache_clear()
    econ = dl.unit_economics()
    assert len(econ) == 60
    # TC-22 and TC-24 are stopped by the gate and have no row; TC-23 reuses
    # RET-2001, which belongs to TC-01 (so the key is still unique).
    assert "RET-2022" not in econ and "RET-2024" not in econ
    assert "RET-2001" in econ
    for tc, lab in LABELS.items():
        if lab["expected_destination"] == "REFURBISH":
            e = econ[BY_TC[tc]["return_id"]]
            net = e["post_refurb_value_usd"] - e["refurb_cost_usd"]
            assert net == float(lab["expected_recovery_usd"]), tc


def test_every_tool_works_for_every_pass_record():
    """No tool raises for any record the agent can receive."""
    import tools
    dl.unit_economics.cache_clear()
    n = 0
    for res in RESULTS:
        if res["gate_status"] != "PASS":
            continue
        rec = res["record"]
        grade = rec["condition_grade"]
        catalog_cat = dl.catalog()[rec["sku"]]["category"]
        tools.get_product_info(rec["sku"])
        tools.get_resale_value(rec["return_id"])
        tools.get_refurb_cost(rec["return_id"])
        assert tools.get_inventory_demand(rec["return_id"])["demand_level"] in {
            "HIGH", "MEDIUM", "LOW"}
        assert isinstance(tools.get_donation_partners(catalog_cat, grade), list)
        tools.get_recycling_rules(catalog_cat)
        for dest in rule_gate.ALL_DESTINATIONS:
            tools.get_carbon_estimate(rec["sku"], dest)
        n += 1
    assert n == 55


# ------------------------------------------- dashboard data (queue.json)
def test_dashboard_queue_json_uses_the_shared_vocabulary():
    """tempHTML/queue.json is pipeline output; every entry validates against
    the same models the agent uses and reproduces the gate's decision."""
    import json
    from models import ReturnRecord
    path = dl.ROOT / "tempHTML" / "queue.json"
    queue = json.loads(path.read_text(encoding="utf-8"))
    assert len(queue) == 64
    expected = {r["record"]["test_case_id"]: r for r in RESULTS}
    for e in queue:
        res = expected[e["test_case_id"]]
        ReturnRecord.model_validate(e["record"])
        assert e["record"] == res["record"]
        assert e["gate"]["gate_status"] == res["gate_status"]
        assert e["gate"]["constraints"] == res["constraints"]
        assert e["needs_human_review"] is True
        rec = e["recommendation"]
        if res["gate_status"] == "PASS":
            r = AgentRecommendation.model_validate(rec)
            allowed = res["constraints"]["allowed_destinations"]
            assert r.recommended_destination in allowed + ["human_review"]
            assert len(r.alternatives) == 5
        else:
            assert rec is None
            assert e["gate"]["proposed_destination"] == "human_review"


def test_dashboard_report_uses_the_shared_destinations():
    import json
    rep = json.loads((dl.ROOT / "tempHTML" / "quarterly_report.json")
                     .read_text(encoding="utf-8"))
    allowed = set(rule_gate.ALL_DESTINATIONS) | {"waste"}
    for q in rep["quarters"]:
        keys = set(q["disposition_breakdown_pct"])
        assert keys <= allowed, keys
        assert sum(q["disposition_breakdown_pct"].values()) == 100


# ---------------------------------------------------- economics loader
def test_missing_economics_raises_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    dl.unit_economics.cache_clear()
    with pytest.raises(dl.MissingDataError, match="unit_economics.csv"):
        dl.unit_economics()
    dl.unit_economics.cache_clear()


def test_economics_loader_parses_rows_and_rejects_duplicates(
        monkeypatch, tmp_path):
    header = ("test_case_id,return_id,resale_as_is_usd,refurb_cost_usd,"
              "post_refurb_value_usd,inventory_demand\n")
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    p = tmp_path / "unit_economics.csv"

    p.write_text(header + "TC-05,RET-2005,100,80,350,high\n")
    dl.unit_economics.cache_clear()
    row = dl.unit_economics()["RET-2005"]
    assert row["refurb_cost_usd"] == 80.0
    assert row["inventory_demand"] == "HIGH"

    p.write_text(header + "TC-01,RET-2001,1,1,1,LOW\nTC-23,RET-2001,1,1,1,LOW\n")
    dl.unit_economics.cache_clear()
    with pytest.raises(dl.MissingDataError, match="Duplicate"):
        dl.unit_economics()
    dl.unit_economics.cache_clear()
