from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from decimal import Decimal, InvalidOperation
from typing import Any

from app.config import Settings
from app.schemas.assistant_tools import (
    AssistantActionType,
    FilterOperator,
    QueryDomain,
    QueryFilter,
    QueryOperation,
    QueryPlan,
)
from app.services.llm.providers import complete_groq_json

PlannerComplete = Callable[..., Awaitable[dict[str, Any]]]

_PROHIBITED_ACTIONS = (
    "delete ",
    "remove document",
    "send whatsapp",
    "send message",
    "cancel session",
    "approve filing",
    "ready for filing",
    "change owner",
)

_METRICS = (
    (("total invoice value", "invoice total", "document value"), "invoice_total"),
    (("taxable value", "taxable amount"), "taxable_value"),
    (("total gst", "total tax", "gst amount", "tax amount"), "total_tax"),
    (("igst",), "igst"),
    (("cgst",), "cgst"),
    (("sgst", "sgst/utgst", "utgst"), "sgst_utgst"),
    (("cess",), "cess"),
)

_DOCUMENT_TYPES = (
    ("purchase & expense invoice", "purchase_expense_invoices"),
    ("purchase and expense invoice", "purchase_expense_invoices"),
    ("credit & debit note", "credit_debit_notes"),
    ("credit and debit note", "credit_debit_notes"),
    ("special transaction", "gst_special_transactions"),
    ("purchase register", "purchase_register"),
    ("sales register", "sales_register"),
    ("purchase invoice", "purchase_expense_invoices"),
    ("sales invoice", "sales_invoices"),
)


def _clarification(message: str) -> QueryPlan:
    return QueryPlan(
        domain=QueryDomain.APPLICATION,
        operation=QueryOperation.CLARIFY,
        clarification=message,
    )


def _metric_from_question(question: str) -> str | None:
    for phrases, field in _METRICS:
        if any(phrase in question for phrase in phrases):
            return field
    return None


def _threshold_filter(question: str, metric: str | None) -> QueryFilter | None:
    match = re.search(
        r"\b(above|over|more than|at least|below|under|less than|at most)\s*"
        r"(?:rs\.?|inr|₹)?\s*([0-9][0-9,]*(?:\.\d+)?)",
        question,
    )
    if not match:
        return None
    try:
        value = format(Decimal(match.group(2).replace(",", "")), "f")
    except InvalidOperation:
        return None
    operator = (
        FilterOperator.GTE
        if match.group(1) in {"above", "over", "more than", "at least"}
        else FilterOperator.LTE
    )
    return QueryFilter(field=metric or "invoice_total", operator=operator, value=value)


def deterministic_plan(question: str) -> QueryPlan:
    normalized = " ".join(question.lower().strip().split())

    if any(phrase in normalized for phrase in _PROHIBITED_ACTIONS):
        return _clarification(
            "I cannot perform that operation. I can only propose approved CA review actions "
            "for explicit confirmation."
        )

    review_match = re.search(
        r"mark\s+reconciliation\s+item\s+([a-z0-9-]+)\s+as\s+reviewed",
        normalized,
    )
    if review_match:
        return QueryPlan(
            domain=QueryDomain.RECONCILIATION,
            operation=QueryOperation.PROPOSE_ACTION,
            action_type=AssistantActionType.MARK_RECONCILIATION_REVIEWED,
            action_parameters={"item_id": review_match.group(1)},
        )

    action_patterns = (
        (
            r"mark\s+validation\s+finding\s+([a-z0-9-]+)\s+as\s+reviewed",
            QueryDomain.VALIDATION,
            AssistantActionType.MARK_VALIDATION_REVIEWED,
            "finding_id",
        ),
        (
            r"raise\s+(?:an?\s+)?alert\s+for\s+reconciliation\s+item\s+([a-z0-9-]+)",
            QueryDomain.RECONCILIATION,
            AssistantActionType.RAISE_RECONCILIATION_ALERT,
            "item_id",
        ),
        (
            r"approve\s+extraction\s+for\s+document\s+([a-z0-9-]+)",
            QueryDomain.EXTRACTIONS,
            AssistantActionType.APPROVE_EXTRACTION,
            "document_id",
        ),
        (
            r"reject\s+extraction\s+for\s+document\s+([a-z0-9-]+)",
            QueryDomain.EXTRACTIONS,
            AssistantActionType.REJECT_EXTRACTION,
            "document_id",
        ),
        (
            r"apply\s+validation\s+correction\s+(?:proposal\s+)?([a-z0-9-]+)",
            QueryDomain.VALIDATION,
            AssistantActionType.APPLY_VALIDATION_CORRECTION,
            "correction_proposal_id",
        ),
    )
    for pattern, domain, action_type, parameter in action_patterns:
        match = re.search(pattern, normalized)
        if match:
            return QueryPlan(
                domain=domain,
                operation=QueryOperation.PROPOSE_ACTION,
                action_type=action_type,
                action_parameters={parameter: match.group(1)},
            )
    if "draft" in normalized and "reminder" in normalized:
        return QueryPlan(
            domain=QueryDomain.CHECKLIST,
            operation=QueryOperation.PROPOSE_ACTION,
            action_type=AssistantActionType.DRAFT_REMINDER,
        )

    if "audit" in normalized or (
        any(word in normalized for word in ("who", "latest", "when"))
        and any(word in normalized for word in ("approved", "reviewed", "uploaded"))
    ):
        return QueryPlan(
            domain=QueryDomain.AUDIT,
            operation=QueryOperation.LIST,
            order_by="created_at",
            order_direction="desc",
            limit=20,
        )

    if any(term in normalized for term in ("gstr-2b", "gstr2b", "reconciliation")):
        filters: list[QueryFilter] = []
        if any(
            phrase in normalized
            for phrase in ("only in gstr", "gstr-2b only", "gstr2b only")
        ):
            filters.append(QueryFilter(field="match_status", value="gstr2b_only"))
        elif "books only" in normalized:
            filters.append(QueryFilter(field="match_status", value="books_only"))
        return QueryPlan(
            domain=QueryDomain.RECONCILIATION,
            operation=QueryOperation.LIST,
            filters=filters,
            limit=50,
        )

    transaction_terms = (
        "invoice",
        "transaction",
        "purchase record",
        "sales record",
        "purchase register",
        "sales register",
        "extracted record",
        "extracted data",
        "portfolio",
        "rcm",
        "taxable value",
        "total gst",
    )
    if any(term in normalized for term in transaction_terms):
        metric = _metric_from_question(normalized)
        minimum = any(word in normalized for word in ("lowest", "least", "minimum", "smallest"))
        maximum = any(word in normalized for word in ("highest", "largest", "maximum"))
        if (minimum or maximum) and "amount" in normalized and metric is None:
            return _clarification(
                "Which amount should I compare: taxable value, total GST, or total invoice value?"
            )

        filters = []
        if "tax invoice" in normalized:
            filters.append(QueryFilter(field="record_kind", value="tax_invoice"))
        for phrase, document_type in _DOCUMENT_TYPES:
            if phrase in normalized:
                filters.append(QueryFilter(field="document_type", value=document_type))
                break
        if "rcm" in normalized:
            filters.append(QueryFilter(field="rcm_flag", value=True))
        if "purchase" in normalized:
            filters.append(QueryFilter(field="invoice_category", value="purchase"))
        elif "sales" in normalized:
            filters.append(QueryFilter(field="invoice_category", value="sales"))

        threshold = _threshold_filter(normalized, metric)
        if threshold:
            filters.append(threshold)

        invoice_match = re.search(
            r"\b([a-z0-9]+(?:[/_-][a-z0-9]+){1,})\b",
            normalized,
        )
        if invoice_match and not any(
            row.field == "invoice_number" for row in filters
        ):
            filters.append(
                QueryFilter(
                    field="invoice_number",
                    operator=FilterOperator.CONTAINS,
                    value=invoice_match.group(1),
                )
            )
        if "need ca review" in normalized or "needs ca review" in normalized:
            filters.append(QueryFilter(field="review_status", value="pending"))

        if any(phrase in normalized for phrase in ("how many", "count of", "number of")):
            operation = QueryOperation.COUNT
        elif minimum:
            operation = QueryOperation.MINIMUM
        elif maximum:
            operation = QueryOperation.MAXIMUM
        elif any(phrase in normalized for phrase in ("average", "mean")):
            operation = QueryOperation.AVERAGE
        elif any(phrase in normalized for phrase in ("summarize", "summary")):
            operation = QueryOperation.SUMMARIZE
        elif normalized.startswith("sum ") or normalized.startswith("what is the total "):
            operation = QueryOperation.SUM
        else:
            operation = QueryOperation.LIST

        effective_metric = metric
        is_extreme = operation in {QueryOperation.MINIMUM, QueryOperation.MAXIMUM}
        if is_extreme and effective_metric is None:
            effective_metric = "invoice_total"
        direction = "desc" if operation == QueryOperation.MAXIMUM else "asc"
        return QueryPlan(
            domain=QueryDomain.TRANSACTIONS,
            operation=operation,
            metric=effective_metric,
            filters=filters,
            order_by=effective_metric if is_extreme else None,
            order_direction=direction,
            limit=1 if is_extreme else 50,
        )

    if "alert" in normalized:
        filters = []
        if "open" in normalized:
            filters.append(QueryFilter(field="status", value="open"))
        return QueryPlan(
            domain=QueryDomain.ALERTS,
            operation=QueryOperation.LIST,
            filters=filters,
            limit=50,
        )
    if any(term in normalized for term in ("validation", "finding", "invalid")):
        filters = []
        if "period" in normalized:
            filters.append(
                QueryFilter(
                    field="finding_type",
                    operator=FilterOperator.CONTAINS,
                    value="period",
                )
            )
        if "open" in normalized or "failed" in normalized:
            filters.append(QueryFilter(field="status", value="open"))
        return QueryPlan(
            domain=QueryDomain.VALIDATION,
            operation=QueryOperation.LIST,
            filters=filters,
            limit=50,
        )
    if any(term in normalized for term in ("missing document", "document checklist", "collection")):
        return QueryPlan(domain=QueryDomain.CHECKLIST, operation=QueryOperation.SUMMARIZE)

    return QueryPlan(
        domain=QueryDomain.APPLICATION_DOCUMENTS,
        operation=QueryOperation.EXPLAIN,
        needs_text_evidence=True,
        needs_knowledge=True,
    )


async def plan_question(
    question: str,
    settings: Settings,
    *,
    groq_complete: PlannerComplete = complete_groq_json,
) -> QueryPlan:
    plan = deterministic_plan(question)
    unresolved = (
        plan.domain == QueryDomain.APPLICATION_DOCUMENTS
        and plan.operation == QueryOperation.EXPLAIN
    )
    if not unresolved or settings.ai_mode == "mock" or not settings.groq_api_key:
        return plan
    contract = {
        "domains": [value.value for value in QueryDomain],
        "operations": [value.value for value in QueryOperation],
        "filter_operators": [value.value for value in FilterOperator],
        "transaction_fields": sorted(
            {
                "document_type",
                "invoice_category",
                "record_kind",
                "supplier_name",
                "supplier_gstin",
                "customer_name",
                "customer_gstin",
                "invoice_number",
                "invoice_date",
                "taxable_value",
                "igst",
                "cgst",
                "sgst_utgst",
                "cess",
                "total_tax",
                "invoice_total",
                "transaction_type",
                "itc_status",
                "rcm_flag",
                "review_status",
            }
        ),
    }
    try:
        output = await asyncio.wait_for(
            groq_complete(
                settings,
                model=settings.effective_groq_rag_model,
                max_tokens=500,
                system_prompt=(
                    "Convert the user question into one JSON QueryPlan. Use only the "
                    "provided contract. Never generate SQL, access rules, or unlisted actions. "
                    "If a money metric is ambiguous, return operation=clarify and a short "
                    "clarification."
                ),
                user_prompt=json.dumps(
                    {"question": question, "contract": contract},
                    separators=(",", ":"),
                ),
            ),
            timeout=min(1.5, settings.rag_generation_timeout_seconds),
        )
        return QueryPlan.model_validate(output)
    except Exception:
        return _clarification(
            "Please rephrase the question with the record type, operation, and exact field "
            "you want me to use."
        )
