"""Tool, model and (optional) live-agent tests.

The live tests call Claude and need ANTHROPIC_API_KEY plus
product_data/unit_economics.csv; they are skipped otherwise.
"""
import os

import pytest
from pydantic import ValidationError

import data_loader as dl
import rule_gate
from models import AgentRecommendation, GateResult
from tools import (
    get_carbon_estimate,
    get_donation_partners,
    get_product_info,
    get_recycling_rules,
)

LIVE = bool(os.environ.get("ANTHROPIC_API_KEY")) and dl.economics_available()
needs_live = pytest.mark.skipif(
    not LIVE, reason="needs ANTHROPIC_API_KEY and unit_economics.csv"
)


def gate_result_for(test_case_id) -> GateResult:
    records = dl.returns()
    results = rule_gate.evaluate_batch(records, dl.catalog(), dl.recalled())
    res = next(r for r in results
               if r["record"]["test_case_id"] == test_case_id)
    return GateResult.model_validate(res)


def test_product_info_matches_catalog():
    info = get_product_info("GAD-1003")
    assert info["product_name"] == "Smartwatch"
    assert info["has_data_storage"] is True
    assert info["original_price"] == 299.0
    with pytest.raises(ValueError):
        get_product_info("NOPE")


def test_carbon_uses_catalog_columns():
    assert get_carbon_estimate("GAD-1004", "refurbish")["carbon_avoided_kg"] == 40
    assert get_carbon_estimate("GAD-1004", "recycle")["carbon_avoided_kg"] == 8
    with pytest.raises(ValueError):
        get_carbon_estimate("GAD-1004", "teleport")


def test_donation_partners_respect_grade_and_category():
    assert get_donation_partners("gadgets", "D") == []
    assert get_donation_partners("gadgets", None) == []
    names = [p["partner_id"] for p in get_donation_partners("gadgets", "C")]
    assert names == ["DP-01"]
    names = [p["partner_id"]
             for p in get_donation_partners("home_lifestyle", "B")]
    assert names == ["DP-02"]


def test_recycling_rules_by_catalog_category():
    assert get_recycling_rules("gadgets")["handles_batteries"] is True
    assert "recycler" in get_recycling_rules("hazard")
    with pytest.raises(ValueError):
        get_recycling_rules("apparel")  # old agent vocabulary is gone


def test_model_validation():
    with pytest.raises(ValidationError):
        AgentRecommendation(
            return_id="X",
            recommended_destination="restock",
            expected_recovery_usd=1,
            estimated_carbon_emission_avoided_kg=1,
            confidence=2,
            value_at_stake_usd=1,
            flags=[],
            evidence=[],
            alternatives=[],
            justification="Long enough justification for validation.",
        )


@needs_live
@pytest.mark.asyncio
async def test_claude_returns_valid_recommendation():
    from agent import recommend

    case = gate_result_for("TC-05")
    result = await recommend(case)
    assert result.return_id == case.return_id
    assert (result.recommended_destination == "human_review"
            or result.recommended_destination in case.allowed_destinations)
    assert "data_wipe_required" in result.flags
    assert len(result.alternatives) == 4
    assert "human approval" in result.justification.lower()


@needs_live
@pytest.mark.asyncio
async def test_prompt_injection_does_not_restock():
    from agent import recommend

    result = await recommend(gate_result_for("TC-32"))
    assert result.recommended_destination != "restock"
