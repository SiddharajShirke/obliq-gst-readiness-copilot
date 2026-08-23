from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class AssistantQuery(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    application_id: str
    conversation_id: UUID = Field(default_factory=uuid4)
    source_type: str | None = None


class Citation(BaseModel):
    source_type: str = "knowledge"
    title: str
    reference: str | None = None
    document_id: str | None = None
    section: str | None = None
    page: int | str | None = None
    sheet_name: str | None = None
    row_start: int | None = None
    row_end: int | None = None
    source_url: str | None = None


class CalculationResult(BaseModel):
    operation: str
    metric: str | None = None
    value: int | str | None = None
    record_count: int = 0


class ToolTraceItem(BaseModel):
    tool: str
    domain: str
    operation: str
    row_count: int = 0


class AssistantAnswer(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    conversation_id: str
    source_types: list[str] = Field(default_factory=list)
    used_application_data: bool = False
    confidence: float = Field(default=0.7, ge=0, le=1)
    calculation: CalculationResult | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    clarification: str | None = None
    proposed_action: dict[str, Any] | None = None
    tool_trace: list[ToolTraceItem] = Field(default_factory=list)


class AssistantModelOutput(BaseModel):
    answer: str
    confidence: float = Field(default=0.7, ge=0, le=1)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: object) -> object:
        if isinstance(value, str):
            labels = {"low": 0.4, "medium": 0.7, "high": 0.9}
            return labels.get(value.strip().lower(), value)
        return value


class KnowledgeTextIngest(BaseModel):
    title: str
    text: str
    source_type: str = "firm_sop"
    source_url: str | None = None
    document_version: str = "demo-v1"
    shared_official: bool = False
