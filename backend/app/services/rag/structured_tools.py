from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.repositories.base import DataStore
from app.schemas.assistant_tools import (
    FilterOperator,
    QueryDomain,
    QueryFilter,
    QueryOperation,
    QueryPlan,
    StructuredToolResult,
)
from app.services.document_collection import get_document_collection_status

_FIELDS: dict[QueryDomain, frozenset[str]] = {
    QueryDomain.TRANSACTIONS: frozenset(
        {
            "id",
            "document_id",
            "document_type",
            "invoice_category",
            "record_kind",
            "supplier_name",
            "supplier_gstin",
            "customer_name",
            "customer_gstin",
            "invoice_number",
            "invoice_date",
            "place_of_supply",
            "taxable_value",
            "gst_rate",
            "igst",
            "cgst",
            "sgst",
            "sgst_utgst",
            "cess",
            "total_tax",
            "invoice_total",
            "transaction_type",
            "itc_status",
            "rcm_flag",
            "original_document_reference",
            "source_page",
            "source_row",
            "review_status",
            "created_at",
        }
    ),
    QueryDomain.VALIDATION: frozenset(
        {"id", "finding_type", "severity", "status", "document_id", "created_at"}
    ),
    QueryDomain.RECONCILIATION: frozenset(
        {"id", "match_status", "review_status", "created_at"}
    ),
    QueryDomain.ALERTS: frozenset(
        {"id", "alert_type", "severity", "status", "reconciliation_item_id", "created_at"}
    ),
    QueryDomain.AUDIT: frozenset(
        {"id", "action", "entity_type", "entity_id", "actor_id", "created_at"}
    ),
    QueryDomain.DOCUMENTS: frozenset(
        {"id", "document_type", "processing_status", "review_status", "created_at"}
    ),
}

_MONEY_FIELDS = frozenset(
    {
        "taxable_value",
        "gst_rate",
        "igst",
        "cgst",
        "sgst",
        "sgst_utgst",
        "cess",
        "total_tax",
        "invoice_total",
    }
)


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _row_value(row: dict[str, Any], field: str) -> Any:
    if field == "record_kind":
        document_type = str(row.get("document_type") or "").strip().lower()
        normalized_type = document_type.replace("_", " ").replace("-", " ")
        if "invoice" in normalized_type and not any(
            note_type in normalized_type for note_type in ("credit note", "debit note")
        ):
            return "tax_invoice"
        return "other"
    if field == "sgst_utgst":
        return row.get("sgst_utgst", row.get("sgst"))
    return row.get(field)


def _matches(row: dict[str, Any], query_filter: QueryFilter) -> bool:
    actual = _row_value(row, query_filter.field)
    expected = query_filter.value
    if query_filter.operator == FilterOperator.IS_NULL:
        return actual in (None, "")
    if query_filter.operator == FilterOperator.NOT_NULL:
        return actual not in (None, "")
    if query_filter.operator == FilterOperator.CONTAINS:
        return str(expected).lower() in str(actual or "").lower()
    if query_filter.operator == FilterOperator.IN:
        values = expected if isinstance(expected, (list, tuple, set)) else [expected]
        return any(str(actual).lower() == str(value).lower() for value in values)
    if query_filter.operator in {FilterOperator.GTE, FilterOperator.LTE}:
        actual_decimal = _decimal(actual)
        expected_decimal = _decimal(expected)
        if actual_decimal is None or expected_decimal is None:
            return False
        if query_filter.operator == FilterOperator.GTE:
            return actual_decimal >= expected_decimal
        return actual_decimal <= expected_decimal
    if isinstance(expected, bool):
        return actual is expected
    return str(actual or "").lower() == str(expected or "").lower()


def _apply_filters(
    rows: list[dict[str, Any]], plan: QueryPlan
) -> list[dict[str, Any]]:
    allowed = _FIELDS.get(plan.domain, frozenset())
    for query_filter in plan.filters:
        if query_filter.field not in allowed:
            raise ValueError(f"Unsupported {plan.domain} filter field: {query_filter.field}")
        rows = [row for row in rows if _matches(row, query_filter)]
    return rows


def _sort_rows(rows: list[dict[str, Any]], plan: QueryPlan) -> list[dict[str, Any]]:
    if not plan.order_by:
        return rows
    allowed = _FIELDS.get(plan.domain, frozenset())
    if plan.order_by not in allowed:
        raise ValueError(f"Unsupported {plan.domain} order field: {plan.order_by}")

    def key(row: dict[str, Any]) -> tuple[bool, Any]:
        value = _row_value(row, plan.order_by or "")
        if plan.order_by in _MONEY_FIELDS:
            parsed = _decimal(value)
            return parsed is None, parsed or Decimal("0")
        return value in (None, ""), str(value or "")

    return sorted(rows, key=key, reverse=plan.order_direction == "desc")


async def _load_rows(
    store: DataStore, application_id: str, domain: QueryDomain
) -> list[dict[str, Any]]:
    if domain == QueryDomain.TRANSACTIONS:
        return await store.list_rows("invoice_records", {"application_id": application_id})
    if domain == QueryDomain.VALIDATION:
        return await store.list_rows("validation_findings", {"application_id": application_id})
    if domain == QueryDomain.ALERTS:
        return await store.list_rows("alerts", {"application_id": application_id})
    if domain == QueryDomain.AUDIT:
        return await store.list_rows(
            "audit_events", {"application_id": application_id}, order="created_at", desc=True
        )
    if domain == QueryDomain.DOCUMENTS:
        return await store.list_rows("documents", {"application_id": application_id})
    if domain == QueryDomain.RECONCILIATION:
        runs = await store.list_rows(
            "reconciliation_runs",
            {"application_id": application_id},
            order="created_at",
            desc=True,
            limit=1,
        )
        if not runs:
            return []
        return await store.list_rows(
            "reconciliation_items", {"reconciliation_run_id": runs[0]["id"]}
        )
    return []


def _citation(domain: QueryDomain, row: dict[str, Any] | None = None) -> dict[str, Any]:
    row = row or {}
    if domain == QueryDomain.RECONCILIATION:
        evidence = row.get("evidence") or {}
        books = evidence.get("books") or {}
        gstr2b = evidence.get("gstr2b") or {}
        identity = books.get("invoice_number") or gstr2b.get("invoice_number")
        return {
            "source_type": "reconciliation",
            "title": f"Reconciliation · {identity or row.get('id', 'summary')}",
            "reference": row.get("id"),
        }
    if domain == QueryDomain.ALERTS:
        return {
            "source_type": "alert",
            "title": f"Alert · {row.get('title') or row.get('alert_type') or 'Application alert'}",
            "reference": row.get("id"),
        }
    labels = {
        QueryDomain.TRANSACTIONS: "Extracted GST records",
        QueryDomain.VALIDATION: "Validation findings",
        QueryDomain.ALERTS: "Raised alerts",
        QueryDomain.AUDIT: "Application audit trail",
        QueryDomain.DOCUMENTS: "Application documents",
        QueryDomain.CHECKLIST: "Document checklist",
    }
    return {
        "source_type": "structured_fact",
        "title": labels.get(domain, "Application facts"),
        "reference": row.get("id"),
    }


async def execute_structured_plan(
    store: DataStore,
    *,
    application_id: str,
    plan: QueryPlan,
) -> StructuredToolResult:
    if plan.operation in {QueryOperation.CLARIFY, QueryOperation.PROPOSE_ACTION}:
        return StructuredToolResult(
            domain=plan.domain,
            operation=plan.operation,
            explanation=plan.clarification,
        )
    if plan.domain == QueryDomain.CHECKLIST:
        collection = await get_document_collection_status(store, application_id)
        return StructuredToolResult(
            domain=plan.domain,
            operation=plan.operation,
            data=collection,
            value=collection.get("missing_count"),
            row_count=int(collection.get("required_count") or 0),
            citations=[_citation(plan.domain)],
        )

    rows = _apply_filters(await _load_rows(store, application_id, plan.domain), plan)
    rows = _sort_rows(rows, plan)
    metric_values = [
        value
        for row in rows
        if plan.metric and (value := _decimal(_row_value(row, plan.metric))) is not None
    ]
    value: Any = None
    selected = rows
    if plan.operation == QueryOperation.COUNT:
        value = len(rows)
    elif plan.operation == QueryOperation.SUM:
        value = sum(metric_values, Decimal("0"))
    elif plan.operation == QueryOperation.AVERAGE:
        value = sum(metric_values, Decimal("0")) / len(metric_values) if metric_values else None
    elif plan.operation == QueryOperation.MINIMUM:
        value = min(metric_values) if metric_values else None
        selected = rows[:1]
    elif plan.operation == QueryOperation.MAXIMUM:
        value = max(metric_values) if metric_values else None
        selected = rows[:1]
    if plan.limit:
        selected = selected[: plan.limit]

    citations = [_citation(plan.domain, row) for row in selected[:5]]
    if not citations:
        citations = [_citation(plan.domain)]
    return StructuredToolResult(
        domain=plan.domain,
        operation=plan.operation,
        data=selected,
        value=value,
        row_count=len(rows),
        citations=citations,
    )
