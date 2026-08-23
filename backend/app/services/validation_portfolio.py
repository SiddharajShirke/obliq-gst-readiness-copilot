"""Categorized live validation portfolio for the six client document requirements."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.repositories.base import DataStore
from app.services.document_processing.taxonomy import CLIENT_REQUIREMENTS

CATEGORY_ORDER = (
    "credit_debit_notes",
    "gst_special_transactions",
    "purchase_expense_invoices",
    "purchase_register",
    "sales_invoices",
    "sales_register",
)


def _label(value: str) -> str:
    return value.replace("_", " ").title()


def _issue_summary(finding: dict[str, Any]) -> str:
    details = finding.get("details") or {}
    if finding.get("finding_type") == "wrong_period":
        return (
            f"Invoice date {details.get('invoice_date') or 'unknown'} is outside the selected "
            f"GST period {details.get('period_start') or 'unknown'} to "
            f"{details.get('period_end') or 'unknown'}."
        )
    if finding.get("finding_type") == "tax_arithmetic_mismatch":
        return (
            f"Recorded total tax {details.get('recorded_total_tax') or 'unknown'} differs from "
            f"the deterministic expected value {details.get('expected_total_tax') or 'unknown'}."
        )
    return str(finding.get("message") or "This extracted record requires CA review.")


async def get_validation_portfolio(store: DataStore, application_id: str) -> dict[str, Any]:
    application = await store.get_row("applications", application_id)
    if not application:
        raise ValueError("Application not found")
    requirements = await store.list_rows(
        "document_requirements", {"application_id": application_id}
    )
    documents = await store.list_rows("documents", {"application_id": application_id})
    records = await store.list_rows("invoice_records", {"application_id": application_id})
    findings = await store.list_rows(
        "validation_findings", {"application_id": application_id}, order="created_at", desc=True
    )
    alerts = await store.list_rows("alerts", {"application_id": application_id})
    alerts = [row for row in alerts if row.get("workflow_area") == "validation"]

    requirement_by_type = {row.get("requirement_type"): row for row in requirements}
    document_by_id = {str(row["id"]): row for row in documents}
    record_by_id = {str(row["id"]): row for row in records}
    enriched_findings: list[dict[str, Any]] = []
    for finding in findings:
        record = record_by_id.get(str(finding.get("invoice_record_id"))) or {}
        document = document_by_id.get(
            str(finding.get("document_id") or record.get("document_id"))
        ) or {}
        enriched_findings.append(
            {
                **finding,
                "evidence_context": {
                    "issue_summary": _issue_summary(finding),
                    "document_name": document.get("original_name"),
                    "document_category": document.get("document_type"),
                    "document_number": record.get("invoice_number"),
                    "party_name": record.get("supplier_name") or record.get("customer_name"),
                    "party_gstin": record.get("supplier_gstin") or record.get("customer_gstin"),
                    "transaction_date": record.get("invoice_date"),
                    "taxable_value": record.get("taxable_value"),
                    "igst": record.get("igst"),
                    "cgst": record.get("cgst"),
                    "sgst": record.get("sgst"),
                    "cess": record.get("cess"),
                    "total_tax": record.get("total_tax"),
                    "document_total": record.get("invoice_total"),
                    "source_page": record.get("source_page"),
                    "source_row": record.get("source_row"),
                    "period_label": application.get("period_label"),
                    "period_start": application.get("period_start"),
                    "period_end": application.get("period_end"),
                },
            }
        )
    findings = enriched_findings
    finding_by_id = {str(row["id"]): row for row in findings}

    def record_category(row: dict[str, Any]) -> str | None:
        document = document_by_id.get(str(row.get("document_id")))
        values = (
            (document or {}).get("document_type"),
            row.get("source_type"),
            row.get("document_type"),
        )
        return next((str(value) for value in values if value in CLIENT_REQUIREMENTS), None)

    category_by_record = {
        record_id: record_category(row) for record_id, row in record_by_id.items()
    }

    def finding_category(row: dict[str, Any]) -> str | None:
        category = category_by_record.get(str(row.get("invoice_record_id")))
        if category:
            return category
        document = document_by_id.get(str(row.get("document_id")))
        value = (document or {}).get("document_type")
        return str(value) if value in CLIENT_REQUIREMENTS else None

    category_by_finding = {
        finding_id: finding_category(row) for finding_id, row in finding_by_id.items()
    }
    categories: list[dict[str, Any]] = []
    for category_type in CATEGORY_ORDER:
        requirement = requirement_by_type.get(category_type)
        category_records = [
            row for row in records if category_by_record.get(str(row["id"])) == category_type
        ]
        category_findings = [
            row for row in findings if category_by_finding.get(str(row["id"])) == category_type
        ]
        category_alerts = [
            row
            for row in alerts
            if category_by_finding.get(str(row.get("validation_finding_id"))) == category_type
        ]
        group_counts = Counter(str(row.get("finding_type") or "other") for row in category_findings)
        open_counts = Counter(
            str(row.get("finding_type") or "other")
            for row in category_findings
            if row.get("status") == "open"
        )
        categories.append(
            {
                "type": category_type,
                "label": CLIENT_REQUIREMENTS[category_type],
                "requirement_status": "received"
                if requirement and requirement.get("status") == "received"
                else "missing",
                "record_count": len(category_records),
                "approved_record_count": sum(
                    row.get("review_status") in {"approved", "edited_and_approved"}
                    for row in category_records
                ),
                "pending_record_count": sum(
                    row.get("review_status") not in {"approved", "edited_and_approved", "rejected"}
                    for row in category_records
                ),
                "finding_count": len(category_findings),
                "open_finding_count": sum(row.get("status") == "open" for row in category_findings),
                "alert_count": len(category_alerts),
                "finding_groups": [
                    {
                        "type": key,
                        "label": _label(key),
                        "count": count,
                        "open_count": open_counts[key],
                    }
                    for key, count in sorted(group_counts.items())
                ],
                "findings": category_findings,
                "alerts": category_alerts,
            }
        )

    categorized_findings = sum(item["finding_count"] for item in categories)
    categorized_open_findings = sum(item["open_finding_count"] for item in categories)
    categorized_records = sum(item["record_count"] for item in categories)
    categorized_approved_records = sum(
        item["approved_record_count"] for item in categories
    )
    return {
        "application_id": application_id,
        "summary": {
            "category_count": len(categories),
            "received_category_count": sum(
                item["requirement_status"] == "received" for item in categories
            ),
            "record_count": categorized_records,
            "approved_record_count": categorized_approved_records,
            "finding_count": categorized_findings,
            "open_finding_count": categorized_open_findings,
            "alert_count": len(alerts),
        },
        "categories": categories,
        "uncategorized_findings": [
            row for row in findings if category_by_finding.get(str(row["id"])) is None
        ],
    }
