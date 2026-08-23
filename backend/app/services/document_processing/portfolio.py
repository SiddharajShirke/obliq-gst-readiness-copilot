"""Deterministic summaries for the six GST extraction portfolios and combined view."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.document_processing.taxonomy import CLIENT_REQUIREMENTS

PORTFOLIO_SCOPES = frozenset((*CLIENT_REQUIREMENTS, "combined"))


def _money(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def is_client_extraction_review_eligible(record: dict[str, Any]) -> bool:
    """Return whether a normalized record may enter the atomic CA bulk-review flow."""

    source_type = record.get("source_type")
    category = (
        source_type
        if source_type in CLIENT_REQUIREMENTS
        else record.get("document_type") or record.get("invoice_category")
    )
    return (
        record.get("review_status") == "pending"
        and category in CLIENT_REQUIREMENTS
        and source_type not in {"gstr2b", "developer_ground_truth"}
    )


def build_portfolio(records: list[dict[str, Any]], scope: str) -> dict[str, Any]:
    if scope not in PORTFOLIO_SCOPES:
        raise ValueError(f"Unsupported portfolio scope: {scope}")
    selected = [
        row
        for row in records
        if scope == "combined" or (row.get("document_type") or row.get("invoice_category")) == scope
    ]
    return {
        "scope": scope,
        "summary": {
            "record_count": len(selected),
            "taxable_value": sum((_money(row.get("taxable_value")) for row in selected), Decimal()),
            "total_tax": sum((_money(row.get("total_tax")) for row in selected), Decimal()),
            "document_value": sum(
                (
                    _money(row.get("invoice_total") or row.get("total_document_value"))
                    for row in selected
                ),
                Decimal(),
            ),
            "approved_count": sum(
                row.get("review_status") in {"approved", "edited_and_approved"} for row in selected
            ),
            "needs_review_count": sum(
                row.get("review_status") not in {"approved", "edited_and_approved"}
                for row in selected
            ),
            "rcm_count": sum(row.get("rcm_flag") is True for row in selected),
        },
        "records": [
            {**row, "review_eligible": is_client_extraction_review_eligible(row)}
            for row in selected
        ],
    }
