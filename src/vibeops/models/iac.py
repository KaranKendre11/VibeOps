from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class CostLineItem(BaseModel):
    description: str
    hourly_usd: float
    monthly_usd: float


class CostEstimate(BaseModel):
    hourly_usd: float
    monthly_usd: float
    source: Literal["infracost", "price_table"]
    confidence: Literal["high", "medium", "low"]
    breakdown: list[CostLineItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    estimated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TerraformValidationResult(BaseModel):
    ok: bool
    errors: list[str] = Field(default_factory=list)


class Violation(BaseModel):
    resource_type: str
    line_number: int = 0  # best-effort; 0 when unavailable


class AllowlistResult(BaseModel):
    ok: bool
    violations: list[Violation] = Field(default_factory=list)


class GeneratedTerraform(BaseModel):
    files: dict[str, str]
    fragment_used: bool = False
