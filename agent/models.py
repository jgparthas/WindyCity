from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

Destination = Literal['restock','refurbish','resell','donate','recycle']

class ReturnRecord(BaseModel):
    return_id: str
    sku: str
    category: Literal['gadgets','apparel','home']
    product_name: str
    original_price_usd: float = Field(ge=0)
    customer_notes: str
    condition_grade: Literal['A','B','C','D'] | None = None

class GateResult(BaseModel):
    status: Literal['PASS','HAZARD','INCOMPLETE']
    allowed_destinations: list[Destination] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    record: ReturnRecord

class OptionAssessment(BaseModel):
    destination: Destination
    eligible: bool
    expected_recovery_usd: float = Field(ge=0)
    carbon_avoided_kg: float = Field(ge=0)
    rationale: str

class AgentRecommendation(BaseModel):
    return_id: str
    recommended_destination: Destination
    expected_recovery_usd: float = Field(ge=0)
    estimated_carbon_emission_avoided_kg: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    value_at_stake_usd: float = Field(ge=0)
    flags: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    alternatives: list[OptionAssessment] = Field(default_factory=list)
    justification: str = Field(min_length=20)
