from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class QueryDomain(StrEnum):
    APPLICATION = "application"
    CHECKLIST = "checklist"
    DOCUMENTS = "documents"
    EXTRACTIONS = "extractions"
    TRANSACTIONS = "transactions"
    VALIDATION = "validation"
    RECONCILIATION = "reconciliation"
    ALERTS = "alerts"
    AUDIT = "audit"
    APPLICATION_DOCUMENTS = "application_documents"
    KNOWLEDGE = "knowledge"


class QueryOperation(StrEnum):
    COUNT = "count"
    SUM = "sum"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    AVERAGE = "average"
    LIST = "list"
    FIND = "find"
    COMPARE = "compare"
    GROUP = "group"
    SUMMARIZE = "summarize"
    EXPLAIN = "explain"
    PROPOSE_ACTION = "propose_action"
    CLARIFY = "clarify"


class FilterOperator(StrEnum):
    EQ = "eq"
    IN = "in"
    GTE = "gte"
    LTE = "lte"
    CONTAINS = "contains"
    IS_NULL = "is_null"
    NOT_NULL = "not_null"


class AssistantActionType(StrEnum):
    APPROVE_EXTRACTION = "approve_extraction"
    REJECT_EXTRACTION = "reject_extraction"
    EDIT_AND_APPROVE_EXTRACTION = "edit_and_approve_extraction"
    APPLY_VALIDATION_CORRECTION = "apply_validation_correction"
    MARK_VALIDATION_REVIEWED = "mark_validation_reviewed"
    MARK_RECONCILIATION_REVIEWED = "mark_reconciliation_reviewed"
    RAISE_RECONCILIATION_ALERT = "raise_reconciliation_alert"
    DRAFT_REMINDER = "draft_reminder"


class QueryFilter(BaseModel):
    field: str
    operator: FilterOperator = FilterOperator.EQ
    value: Any = None


class QueryPlan(BaseModel):
    domain: QueryDomain
    operation: QueryOperation
    metric: str | None = None
    filters: list[QueryFilter] = Field(default_factory=list, max_length=12)
    group_by: str | None = None
    order_by: str | None = None
    order_direction: Literal["asc", "desc"] = "asc"
    limit: int | None = Field(default=None, ge=1, le=100)
    needs_text_evidence: bool = False
    needs_knowledge: bool = False
    clarification: str | None = None
    action_type: AssistantActionType | None = None
    action_parameters: dict[str, Any] = Field(default_factory=dict)


class StructuredToolResult(BaseModel):
    domain: QueryDomain
    operation: QueryOperation
    data: Any = None
    value: Any = None
    row_count: int = 0
    citations: list[dict[str, Any]] = Field(default_factory=list)
    explanation: str | None = None
