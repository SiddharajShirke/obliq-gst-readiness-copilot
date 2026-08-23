"""Deterministic CA-preparatory readiness and report evidence aggregation."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.repositories.base import DataStore
from app.services.document_processing.taxonomy import CLIENT_REQUIREMENTS
from app.services.workflow_progress import get_workflow_progress

EXCLUDED_REPORT_TYPES = frozenset({"developer_ground_truth"})


def _number(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def total(*keys: str) -> Decimal:
        return sum(
            (
                _number(next((row.get(key) for key in keys if row.get(key) is not None), 0))
                for row in rows
            ),
            Decimal("0"),
        )

    tax_total = sum(
        (
            _number(row.get("igst"))
            + _number(row.get("cgst"))
            + _number(row.get("sgst", row.get("sgst_utgst")))
            + _number(row.get("cess"))
            for row in rows
        ),
        Decimal("0"),
    )
    return {
        "invoice_count": len(rows),
        "taxable_value": float(total("taxable_value")),
        "cgst": float(total("cgst")),
        "sgst": float(total("sgst", "sgst_utgst")),
        "igst": float(total("igst")),
        "cess": float(total("cess")),
        "tax_total": float(tax_total),
        "invoice_total": float(total("invoice_total", "total_document_value")),
        "rcm_count": sum(bool(row.get("rcm_flag")) for row in rows),
        "itc_not_available_count": sum(
            str(row.get("itc_status") or "").lower() in {"not_available", "itc_not_available"}
            for row in rows
        ),
    }


async def build_readiness_summary(
    store: DataStore,
    *,
    application: dict[str, Any],
    client: dict[str, Any],
) -> dict[str, Any]:
    application_id = str(application["id"])
    requirements = await store.list_rows(
        "document_requirements", {"application_id": application_id}, order="label"
    )
    stored_documents = await store.list_rows(
        "documents", {"application_id": application_id}, order="created_at"
    )
    documents = [
        row for row in stored_documents if row.get("document_type") not in EXCLUDED_REPORT_TYPES
    ]
    stored_invoices = await store.list_rows(
        "invoice_records", {"application_id": application_id}, order="created_at"
    )
    invoices = [
        row
        for row in stored_invoices
        if row.get("source_type") not in EXCLUDED_REPORT_TYPES
        and row.get("document_type") not in EXCLUDED_REPORT_TYPES
    ]
    findings = await store.list_rows(
        "validation_findings", {"application_id": application_id}, order="created_at"
    )
    runs = await store.list_rows(
        "reconciliation_runs",
        {"application_id": application_id},
        order="created_at",
        desc=True,
        limit=1,
    )
    reconciliation_items = (
        await store.list_rows("reconciliation_items", {"reconciliation_run_id": runs[0]["id"]})
        if runs
        else []
    )
    alerts = await store.list_rows(
        "alerts", {"application_id": application_id}, order="created_at", desc=True
    )
    audits = await store.list_rows(
        "audit_events", {"application_id": application_id}, order="created_at", desc=True
    )
    firm = await store.get_row("firms", application["firm_id"])
    workflow = await get_workflow_progress(store, application_id)

    document_by_id = {str(row["id"]): row for row in documents}
    invoice_by_id = {str(row["id"]): row for row in invoices}
    requirement_by_id = {str(row["id"]): row for row in requirements}
    manifest = [
        {
            "document_id": row["id"],
            "document_type": row.get("document_type"),
            "category": (
                requirement_by_id.get(str(row.get("requirement_id")), {}).get("label")
                or CLIENT_REQUIREMENTS.get(str(row.get("document_type")))
                or str(row.get("document_type") or "Unknown").replace("_", " ").title()
            ),
            "original_name": row.get("original_name"),
            "uploaded_at": row.get("upload_completed_at") or row.get("created_at"),
            "source": row.get("source"),
            "status": row.get("processing_status"),
        }
        for row in documents
    ]

    enriched_findings: list[dict[str, Any]] = []
    for finding in findings:
        record = invoice_by_id.get(str(finding.get("invoice_record_id")))
        document = document_by_id.get(
            str(finding.get("document_id") or (record or {}).get("document_id"))
        )
        enriched_findings.append(
            {
                **finding,
                "validation_finding_id": finding.get("id"),
                "invoice_number": (record or {}).get("invoice_number"),
                "document_name": (document or {}).get("original_name"),
                "resolution": "Reviewed by CA"
                if finding.get("status") in {"resolved", "accepted"}
                else None,
            }
        )

    business_invoices = [
        row
        for row in invoices
        if row.get("invoice_category") != "gstr2b" and row.get("source_type") != "gstr2b"
    ]
    sales = [row for row in business_invoices if row.get("invoice_category") == "sales"]
    purchases = [row for row in business_invoices if row.get("invoice_category") == "purchase"]
    category_summaries = {
        key: _aggregate(
            [
                row
                for row in business_invoices
                if row.get("document_type") == key or row.get("source_type") == key
            ]
        )
        for key in CLIENT_REQUIREMENTS
    }
    reviewed_findings = sum(row.get("status") in {"resolved", "accepted"} for row in findings)
    resolved_findings = sum(row.get("status") == "resolved" for row in findings)
    reconciliation_status = workflow["reconciliation"]["status"]

    return {
        "client": client,
        "application": application,
        "firm": firm or {"name": "CA firm"},
        "generated_at": datetime.now(UTC).isoformat(),
        "documents": {
            "required": sum(bool(row.get("required")) for row in requirements),
            "received": sum(
                bool(row.get("required")) and row.get("status") == "received"
                for row in requirements
            ),
            "reviewed": sum(
                row.get("processing_status") == "approved"
                for row in documents
                if row.get("document_type") != "gstr2b"
            ),
            "requirements": requirements,
            "missing_labels": [
                row["label"]
                for row in requirements
                if row.get("required") and row.get("status") != "received"
            ],
        },
        "document_manifest": manifest,
        "normalized_records": business_invoices,
        "sales_records": sales,
        "purchase_records": purchases,
        "sales": _aggregate(sales),
        "purchases": _aggregate(purchases),
        "category_summaries": category_summaries,
        "validation": {
            "finding_count": len(findings),
            "reviewed_count": reviewed_findings,
            "resolved_count": resolved_findings,
            "open_count": len(findings) - reviewed_findings,
            "progress_percent": workflow["validation"]["progress_percent"],
            "findings": enriched_findings,
        },
        "reconciliation": {
            "status": reconciliation_status,
            "review_percent": workflow["reconciliation"]["progress_percent"],
            "summary": (runs[0].get("summary") if runs else {}) or {},
            "run": runs[0] if runs else None,
        },
        "reconciliation_items": reconciliation_items,
        "alerts": alerts,
        "readiness": workflow["readiness"],
        "workflow": workflow,
        "audit_summary": audits[:50],
        "readiness_status": "ready_for_filing"
        if workflow["readiness"]["ready_for_filing"]
        else "validation_review_required",
        "disclaimer": (
            "GST preparation report generated by OBLIQ for CA review. Final filing and "
            "professional GST decisions remain subject to CA verification."
        ),
    }
