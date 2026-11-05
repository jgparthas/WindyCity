"""Schemas shared by the Rule Gate, the agent, and the review queue.

Field names and enums mirror rule_gate/rule_gate.py and product_data/ exactly,
so a gate result validates here with no translation. See docs/CONTRACT.md.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Destination = Literal['restock', 'refurbish', 'donate', 'recycle', 'waste']
# The agent may also hand the item to a person. human_review is never a
# member of the gate's allowed_destinations.
Outcome = Literal['restock', 'refurbish', 'donate', 'recycle', 'waste',
                  'human_review']
Category = Literal['gadgets', 'fashion', 'home_lifestyle']
Grade = Literal['A', 'B', 'C', 'D']
GateStatus = Literal['PASS', 'HAZARD', 'INCOMPLETE']
Severity = Literal['BLOCK', 'CONSTRAIN', 'WARN']
Channel = Literal['warehouse', 'store']
ReasonCode = Literal['defective', 'damaged_in_transit', 'not_as_described',
                     'wrong_item_received', 'changed_mind', 'size_or_fit',
                     'other']


class ReturnRecord(BaseModel):
    """The return record exactly as the gate receives and echoes it."""
    model_config = ConfigDict(extra='ignore')

    return_id: str
    sku: str
    category: Category
    product_name: str
    original_price: float = Field(ge=0)
    purchase_date: str
    received_at: str  # local receiving-site time, no timezone suffix
    received_channel: Channel
    return_reason_code: ReasonCode
    customer_notes: str | None = None  # untrusted free text
    condition_grade: Grade | None = None
    hazard_flags: list[str] = Field(default_factory=list)
    data_wipe_confirmed: bool | None = None
    test_case_id: str | None = None  # synthetic data only


class GateReason(BaseModel):
    rule_id: str
    severity: Severity
    message: str


class GateConstraints(BaseModel):
    allowed_destinations: list[Destination] = Field(default_factory=list)
    data_wipe_required: bool = False


class GateResult(BaseModel):
    """One Rule Gate output object (rule_gate.evaluate)."""
    model_config = ConfigDict(extra='ignore')

    return_id: str
    gate_status: GateStatus
    route: Literal['agent', 'review_queue']
    proposed_destination: Literal['human_review'] | None = None
    reasons: list[GateReason] = Field(default_factory=list)
    constraints: GateConstraints = Field(default_factory=GateConstraints)
    record: ReturnRecord
    rule_version: str
    evaluated_at: str

    @property
    def allowed_destinations(self) -> list[str]:
        return self.constraints.allowed_destinations


class OptionAssessment(BaseModel):
    destination: Destination
    eligible: bool
    expected_recovery_usd: float = Field(ge=0)
    carbon_avoided_kg: float = Field(ge=0)
    rationale: str


class AgentRecommendation(BaseModel):
    return_id: str
    test_case_id: str | None = None
    recommended_destination: Outcome
    needs_review: bool = False
    expected_recovery_usd: float = Field(ge=0)
    estimated_carbon_emission_avoided_kg: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    value_at_stake_usd: float = Field(ge=0)
    flags: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    alternatives: list[OptionAssessment] = Field(default_factory=list)
    justification: str = Field(min_length=20)
