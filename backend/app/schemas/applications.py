from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator


class ApplicationCreate(BaseModel):
    financial_year: str = Field(min_length=7, max_length=9)
    period_label: str = Field(min_length=3, max_length=80)
    period_start: date
    period_end: date
    filing_frequency: str = Field(pattern="^(monthly|quarterly)$")
    due_date: date | None = None
    assigned_preparer_id: str | None = None
    reviewer_id: str | None = None

    @model_validator(mode="after")
    def validate_period(self) -> "ApplicationCreate":
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self


class ApplicationUpdate(BaseModel):
    due_date: date | None = None
    status: str | None = None
    assigned_preparer_id: str | None = None
    reviewer_id: str | None = None
    filing_date: date | None = None
    arn: str | None = None
    final_notes: str | None = None
