from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class FindingResolution(BaseModel):
    status: str = Field(pattern="^(resolved|accepted)$")


class ReturnToPreparer(BaseModel):
    notes: str = Field(min_length=3, max_length=2000)


class FilingEvidenceInput(BaseModel):
    filing_date: date
    arn: str = Field(min_length=4, max_length=80)
    final_notes: str | None = None
