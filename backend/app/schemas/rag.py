from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AssistantQuery(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    application_id: str | None = None
    source_type: str | None = None


class Citation(BaseModel):
    title: str
    section: str | None = None
    page: int | str | None = None
    source_url: str | None = None


class AssistantAnswer(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    used_application_data: bool = False
    confidence: float = Field(default=0.7, ge=0, le=1)


class KnowledgeTextIngest(BaseModel):
    title: str
    text: str
    source_type: str = "firm_sop"
    source_url: str | None = None
    document_version: str = "demo-v1"
    shared_official: bool = False
