from models import AgentRecommendation, GateResult, OptionAssessment
from tools import (
    get_carbon_estimate,
    get_donation_partners,
    get_inventory_demand,
    get_product_info,
    get_recycling_rules,
    get_refurb_cost,
    get_resale_value,
)

DEMAND_FACTOR = {
    "HIGH": 1.00,
    "MEDIUM": 0.82,
    "LOW": 0.55,
}


def _log_tool(name: str, result):
    print(f"[TOOL] {name} -> {result}")
    return result


def _carbon_avoided(destination: str, category: str) -> float:
    result = get_carbon_estimate(destination, category)
    return result["carbon_avoided_kg"]


def recommend(gate_result: GateResult) -> AgentRecommendation:
    if gate_result.status != "PASS":
        raise ValueError(
            f"Agent bypassed: gate status is {gate_result.status}."
        )

    record = gate_result.record
    if record.condition_grade is None:
        raise ValueError(
            "Agent requires a condition grade after the Rule Gate."
        )

    product = _log_tool(
        "get_product_info",
        get_product_info(record.sku),
    )
    resale = _log_tool(
        "get_resale_value",
        get_resale_value(record.sku, record.condition_grade),
    )
    refurb = _log_tool(
        "get_refurb_cost",
        get_refurb_cost(record.sku, record.condition_grade),
    )
    demand = _log_tool(
        "get_inventory_demand",
        get_inventory_demand(record.sku),
    )
    partners = _log_tool(
        "get_donation_partners",
        get_donation_partners(record.category, record.condition_grade),
    )
    recycling = _log_tool(
        "get_recycling_rules",
        get_recycling_rules(record.category),
    )

    market_value = resale["estimated_resale_usd"]
    refurb_cost = refurb["estimated_refurb_cost_usd"]
    demand_factor = DEMAND_FACTOR[demand["demand_level"]]
    allowed = set(gate_result.allowed_destinations)

    option_policy = {
        "restock": (
            record.condition_grade == "A",
            market_value * demand_factor,
            "Eligible only for like-new grade A items.",
        ),
        "refurbish": (
            record.category == "gadgets"
            and record.condition_grade in {"B", "C"}
            and refurb_cost < market_value * 0.45,
            max(0, market_value - refurb_cost) * demand_factor,
            "Requires a repairable B/C gadget with repair cost below "
            "45% of market value.",
        ),
        "resell": (
            record.condition_grade in {"A", "B", "C"},
            market_value * 0.72 * demand_factor,
            "As-is resale is discounted for channel fees, condition "
            "risk, and demand.",
        ),
        "donate": (
            bool(partners) and record.condition_grade in {"B", "C"},
            min(market_value * 0.20, 20.0),
            "Donation is eligible when a Cosmic Nexus partner accepts "
            "the usable item.",
        ),
        "recycle": (
            True,
            0.0,
            "Recycling is the fallback when safe reuse paths are not "
            "economically viable.",
        ),
    }

    assessments = []
    scores = {}

    for destination, policy in option_policy.items():
        meets_policy, recovery, rationale = policy
        eligible = meets_policy and destination in allowed
        carbon_avoided = _carbon_avoided(destination, record.category)

        assessment = OptionAssessment(
            destination=destination,
            eligible=eligible,
            expected_recovery_usd=(
                round(recovery, 2) if eligible else 0
            ),
            carbon_avoided_kg=carbon_avoided,
            rationale=rationale,
        )
        assessments.append(assessment)

        if eligible:
            sustainability_bonus = carbon_avoided * 0.15
            scores[destination] = round(
                recovery + sustainability_bonus,
                2,
            )

    if not scores:
        raise ValueError(
            "No eligible destination remains after constraints."
        )

    ranked_destinations = sorted(
        scores,
        key=scores.get,
        reverse=True,
    )
    selected_destination = ranked_destinations[0]
    selected = next(
        item
        for item in assessments
        if item.destination == selected_destination
    )

    runner_up = (
        ranked_destinations[1]
        if len(ranked_destinations) > 1
        else None
    )
    if runner_up is None:
        value_at_stake = 0.0
    else:
        value_at_stake = round(
            scores[selected_destination] - scores[runner_up],
            2,
    )

    _log_tool(
        "get_carbon_estimate",
        {
            "destination": selected_destination,
            "category": record.category,
            "carbon_avoided_kg": selected.carbon_avoided_kg,
        },
    )

    flags = list(gate_result.constraints)

    if runner_up is None:
        confidence = 0.9
    elif value_at_stake >= 15:
        confidence = 0.9
    elif value_at_stake >= 5:
        confidence = 0.75
    else:
        confidence = 0.6
        flags.append("close_tradeoff_review")

    if demand["demand_level"] == "LOW":
        flags.append("low_demand")

    evidence = [
        f"Condition grade: {record.condition_grade}",
        f"Market value: ${market_value:.2f}",
        f"Refurbishment cost: ${refurb_cost:.2f}",
        (
            f"Demand: {demand['demand_level']} with "
            f"{demand['units_on_hand']} units on hand"
        ),
        (
            f"Nearest eligible donation partner: "
            f"{partners[0]['name']} at {partners[0]['distance_km']} km"
            if partners
            else "No eligible donation partner"
        ),
        f"Recycling requirements: {recycling}",
        f"Product data storage: {product['has_data_storage']}",
    ]

    comparison = ""
    if runner_up:
        comparison = (
            f" It leads {runner_up} by {value_at_stake:.2f} "
            "modeled score points."
        )

    justification = (
        f"Recommend {selected_destination}: modeled recovery is "
        f"${selected.expected_recovery_usd:.2f}, demand is "
        f"{demand['demand_level']}, and estimated carbon avoided is "
        f"{selected.carbon_avoided_kg:.1f} kg."
        f"{comparison} The recommendation respects Rule Gate "
        "constraints and requires human approval."
    )

    return AgentRecommendation(
        return_id=record.return_id,
        recommended_destination=selected_destination,
        expected_recovery_usd=selected.expected_recovery_usd,
        estimated_carbon_emission_avoided_kg=(
            selected.carbon_avoided_kg
        ),
        confidence=confidence,
        value_at_stake_usd=value_at_stake,
        flags=flags,
        evidence=evidence,
        alternatives=assessments,
        justification=justification,
    )
