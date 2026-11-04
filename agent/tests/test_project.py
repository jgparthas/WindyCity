import pytest
from pydantic import ValidationError

from agent import recommend
from models import AgentRecommendation, GateResult, ReturnRecord
from tools import (
    get_carbon_estimate,
    get_donation_partners,
    get_inventory_demand,
    get_product_info,
    get_refurb_cost,
    get_resale_value,
)


def make_case(
    return_id,
    sku,
    category,
    grade,
    allowed,
    constraints=None,
):
    return GateResult(
        status="PASS",
        allowed_destinations=allowed,
        constraints=constraints or [],
        record=ReturnRecord(
            return_id=return_id,
            sku=sku,
            category=category,
            product_name="Test item",
            original_price_usd=100,
            customer_notes="Test notes",
            condition_grade=grade,
        ),
    )


def test_tools():
    assert get_product_info("GAD-1002")["has_data_storage"] is True

    assert (
        get_resale_value("GAD-1002", "C")["estimated_resale_usd"]
        == 82.5
    )

    assert (
        get_refurb_cost("GAD-1002", "C")["estimated_refurb_cost_usd"]
        == 21.0
    )

    assert (
        get_inventory_demand("GAD-1002")["demand_level"]
        == "HIGH"
    )

    assert get_donation_partners("gadgets", "D") == []

    assert (
        get_carbon_estimate("refurbish", "gadgets")[
            "carbon_avoided_kg"
        ]
        == 14.0
    )

    with pytest.raises(ValueError):
        get_product_info("NOPE")


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


@pytest.mark.asyncio
async def test_claude_returns_valid_recommendation():
    case = make_case(
        "RET-TEST-001",
        "GAD-1002",
        "gadgets",
        "C",
        [
            "restock",
            "refurbish",
            "resell",
            "donate",
            "recycle",
        ],
        constraints=["data_wipe_required"],
    )

    result = await recommend(case)

    assert result.return_id == "RET-TEST-001"

    assert (
        result.recommended_destination
        in case.allowed_destinations
    )

    assert 0.0 <= result.confidence <= 1.0

    assert result.expected_recovery_usd >= 0
    assert result.estimated_carbon_emission_avoided_kg >= 0
    assert result.value_at_stake_usd >= 0

    assert result.justification
    assert len(result.evidence) > 0
    assert len(result.alternatives) > 0


@pytest.mark.asyncio
async def test_recommendation_has_reasoning_evidence():
    case = make_case(
        "RET-TEST-002",
        "GAD-1002",
        "gadgets",
        "C",
        [
            "restock",
            "refurbish",
            "resell",
            "donate",
            "recycle",
        ],
    )

    result = await recommend(case)

    assert len(result.evidence) >= 5
    assert len(result.alternatives) == 5

    assert (
        "human approval"
        in result.justification.lower()
    )