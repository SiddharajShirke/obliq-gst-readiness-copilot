from __future__ import annotations

from pydantic import BaseModel, Field


class AlertExplanation(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    what_happened: str = Field(min_length=3, max_length=1000)
    why_flagged: str = Field(min_length=3, max_length=1000)
    what_ca_should_review: str = Field(min_length=3, max_length=1000)
    short_summary: str = Field(min_length=3, max_length=300)


class AlertStatusUpdate(BaseModel):
    status: str = Field(pattern="^(acknowledged|resolved)$")
