from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


class FindingResolution(BaseModel):
    status: str = Field(pattern="^(resolved|accepted)$")


class BulkFindingResolution(BaseModel):
    finding_ids: list[str] = Field(min_length=1, max_length=500)
    status: Literal["resolved", "accepted"]


class BulkReconciliationReview(BaseModel):
    item_ids: list[str] = Field(min_length=1, max_length=500)
    action: Literal["mark_reviewed"] = "mark_reviewed"


class ReturnToPreparer(BaseModel):
    notes: str = Field(min_length=3, max_length=2000)


class FilingEvidenceInput(BaseModel):
    filing_date: date
    arn: str = Field(min_length=4, max_length=80)
    final_notes: str | None = None


class ValidationCorrectionRequest(BaseModel):
    mode: Literal["manual", "ai"]
    record_ids: list[str] = Field(min_length=1, max_length=200)
    changes: dict[str, Any] = Field(default_factory=dict)
    finding_ids: list[str] = Field(default_factory=list, max_length=200)
    rationale: str | None = Field(default=None, max_length=2000)
