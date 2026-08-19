"""GST readiness summary from structured, reviewed application data."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.repositories.base import DataStore


def _number(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "invoice_count": len(rows),
        "taxable_value": float(sum((_number(row.get("taxable_value")) for row in rows), Decimal("0"))),
        "cgst": float(sum((_number(row.get("cgst")) for row in rows), Decimal("0"))),
        "sgst": float(sum((_number(row.get("sgst")) for row in rows), Decimal("0"))),
        "igst": float(sum((_number(row.get("igst")) for row in rows), Decimal("0"))),
        "cess": float(sum((_number(row.get("cess")) for row in rows), Decimal("0"))),
        "tax_total": float(
            sum(
                (
                    _number(row.get("cgst"))
                    + _number(row.get("sgst"))
                    + _number(row.get("igst"))
                    + _number(row.get("cess"))
                    for row in rows
                ),
                Decimal("0"),
            )
        ),
        "invoice_total": float(sum((_number(row.get("invoice_total")) for row in rows), Decimal("0"))),
    }


async def build_readiness_summary(
    store: DataStore,
    *,
    application: dict[str, Any],
    client: dict[str, Any],
) -> dict[str, Any]:
    requirements = await store.list_rows("document_requirements", {"application_id": application["id"]})
    documents = await store.list_rows("documents", {"application_id": application["id"]})
    invoices = await store.list_rows("invoice_records", {"application_id": application["id"]})
    findings = await store.list_rows(
        "validation_findings", {"application_id": application["id"], "status": "open"}
    )
    runs = await store.list_rows(
        "reconciliation_runs",
        {"application_id": application["id"]},
        order="created_at",
        desc=True,
        limit=1,
    )
    audits = await store.list_rows(
        "audit_events", {"application_id": application["id"]}, order="created_at", desc=True
    )

    sales = [row for row in invoices if row.get("invoice_category") == "sales"]
    purchases = [row for row in invoices if row.get("invoice_category") == "purchase"]
    sales_summary = _aggregate(sales)
    purchase_summary = _aggregate(purchases)
    estimated_liability = max(sales_summary["tax_total"] - purchase_summary["tax_total"], 0.0)
    missing = [row["label"] for row in requirements if row.get("required") and row.get("status") == "missing"]

    return {
        "client": client,
        "application": application,
        "documents": {
            "required": sum(bool(row.get("required")) for row in requirements),
            "received": sum(row.get("status") != "missing" for row in requirements),
            "reviewed": sum(row.get("processing_status") == "approved" for row in documents),
            "missing_labels": missing,
        },
        "sales": sales_summary,
        "purchases": purchase_summary,
        "potential_input_tax": purchase_summary["tax_total"],
        "output_tax": sales_summary["tax_total"],
        "estimated_liability": round(estimated_liability, 2),
        "reconciliation": (runs[0].get("summary") if runs else {}) or {},
        "open_issues": findings,
        "approval_status": application.get("status"),
        "audit_summary": audits[:20],
        "readiness_status": "ca_action_required" if missing or findings else "ready_for_ca_review",
        "disclaimer": "Estimated from uploaded data and subject to CA review. OBLIQ does not determine final GST liability or ITC eligibility.",
    }
