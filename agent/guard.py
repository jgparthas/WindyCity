"""Deterministic checks applied to the agent's output after the model
responds. No SDK dependency, so they can be tested offline."""
from models import AgentRecommendation, GateResult


def enforce_gate(
    recommendation: AgentRecommendation, gate_result: GateResult
) -> AgentRecommendation:
    """Reject recommendations the gate does not allow and carry gate
    constraints through to the reviewer. Mutates and returns the copy."""
    if gate_result.gate_status != "PASS":
        raise ValueError(
            f"Agent bypassed: gate status is {gate_result.gate_status}."
        )

    if recommendation.return_id != gate_result.return_id:
        raise ValueError(
            "Recommendation return_id does not match the gate result."
        )

    dest = recommendation.recommended_destination
    if dest != "human_review" and dest not in gate_result.allowed_destinations:
        raise ValueError(
            f"Agent selected '{dest}', which the Rule Gate does not allow."
        )

    flags = list(recommendation.flags)
    if gate_result.constraints.data_wipe_required and \
            "data_wipe_required" not in flags:
        flags.append("data_wipe_required")

    needs_review = recommendation.needs_review or dest == "human_review"
    if needs_review and "human_review_required" not in flags:
        flags.append("human_review_required")

    return recommendation.model_copy(update={
        "flags": flags,
        "needs_review": needs_review,
        "test_case_id": gate_result.record.test_case_id,
    })
