"""Application-scoped transition from CA extraction review to validation review."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.repositories.base import DataStore
from app.services.validation import InvoiceInput, detect_duplicate_groups, validate_invoice

APPROVED_REVIEW_STATUSES = frozenset({"approved", "edited_and_approved"})
REVIEWED_REVIEW_STATUSES = frozenset({*APPROVED_REVIEW_STATUSES, "rejected"})
EXCLUDED_VALIDATION_SOURCES = frozenset({"gstr2b", "developer_ground_truth"})


def is_client_validation_record(row: dict[str, Any]) -> bool:
    return not any(
        row.get(field) in EXCLUDED_VALIDATION_SOURCES for field in ("source_type", "document_type")
    )


@dataclass(slots=True)
class ValidationWorkflowResult:
    current_stage: str
    validation_ran: bool
    record_count: int
    approved_record_count: int
    rejected_record_count: int
    pending_record_count: int
    eligible_record_count: int = 0
    findings: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "current_stage": self.current_stage,
            "validation_ran": self.validation_ran,
            "record_count": self.record_count,
            "approved_record_count": self.approved_record_count,
            "rejected_record_count": self.rejected_record_count,
            "pending_record_count": self.pending_record_count,
            "pending_review_count": self.pending_record_count,
            "eligible_record_count": self.eligible_record_count,
            "finding_count": len(self.findings),
            "findings": self.findings,
        }


def _date(value: Any) -> date:
    return date.fromisoformat(str(value)[:10])


def _invoice_input(row: dict[str, Any]) -> InvoiceInput:
    return InvoiceInput(
        supplier_name=row.get("supplier_name"),
        supplier_gstin=row.get("supplier_gstin"),
        customer_name=row.get("customer_name"),
        customer_gstin=row.get("customer_gstin"),
        invoice_number=row.get("invoice_number"),
        invoice_date=_date(row["invoice_date"]) if row.get("invoice_date") else None,
        taxable_value=row.get("taxable_value"),
        cgst=row.get("cgst"),
        sgst=row.get("sgst", row.get("sgst_utgst")),
        igst=row.get("igst"),
        cess=row.get("cess"),
        invoice_total=row.get("invoice_total", row.get("total_document_value")),
        metadata={"record_id": row["id"]},
    )


async def run_application_validation(
    store: DataStore,
    *,
    application_id: str,
    firm_id: str,
) -> ValidationWorkflowResult:
    application = await store.get_row("applications", application_id)
    if not application or str(application.get("firm_id")) != str(firm_id):
        raise ValueError("Application not found")
    client = await store.get_row("clients", application["client_id"])
    if not client:
        raise ValueError("Application client not found")

    stored_records = await store.list_rows("invoice_records", {"application_id": application_id})
    all_records = [row for row in stored_records if is_client_validation_record(row)]
    records = [row for row in all_records if row.get("review_status") in APPROVED_REVIEW_STATUSES]
    old_findings = await store.list_rows("validation_findings", {"application_id": application_id})
    for finding in old_findings:
        await store.delete_row("validation_findings", finding["id"])

    inserted: list[dict[str, Any]] = []
    inputs: list[InvoiceInput] = []
    record_map: dict[str, dict[str, Any]] = {}
    for row in records:
        invoice = _invoice_input(row)
        inputs.append(invoice)
        record_map[row["id"]] = row
        expected = client.get("gstin") if row.get("invoice_category") == "sales" else None
        for finding in validate_invoice(
            invoice,
            period_start=_date(application["period_start"]),
            period_end=_date(application["period_end"]),
            expected_customer_gstin=expected,
        ):
            inserted.append(
                await store.insert_row(
                    "validation_findings",
                    {
                        "firm_id": firm_id,
                        "application_id": application_id,
                        "document_id": row.get("document_id"),
                        "invoice_record_id": row["id"],
                        "finding_type": finding.finding_type,
                        "severity": finding.severity,
                        "message": finding.message,
                        "details": finding.details,
                        "status": "open",
                    },
                )
            )

    for group in detect_duplicate_groups(inputs):
        record_ids = [str(item.metadata["record_id"]) for item in group]
        inserted.append(
            await store.insert_row(
                "validation_findings",
                {
                    "firm_id": firm_id,
                    "application_id": application_id,
                    "document_id": record_map[record_ids[0]].get("document_id"),
                    "invoice_record_id": record_ids[0],
                    "finding_type": "duplicate_invoice",
                    "severity": "medium",
                    "message": "A possible duplicate invoice was detected.",
                    "details": {"invoice_record_ids": record_ids},
                    "status": "open",
                },
            )
        )

    await store.update_row("applications", application_id, {"status": "validation_review"})
    rejected_count = sum(row.get("review_status") == "rejected" for row in all_records)
    pending_count = sum(
        row.get("review_status") not in REVIEWED_REVIEW_STATUSES for row in all_records
    )
    return ValidationWorkflowResult(
        current_stage="validation_review",
        validation_ran=True,
        record_count=len(all_records),
        approved_record_count=len(records),
        rejected_record_count=rejected_count,
        pending_record_count=pending_count,
        eligible_record_count=len(records),
        findings=inserted,
    )


async def advance_after_extraction_review(
    store: DataStore,
    *,
    application_id: str,
    firm_id: str,
) -> ValidationWorkflowResult:
    application = await store.get_row("applications", application_id)
    if not application or str(application.get("firm_id")) != str(firm_id):
        raise ValueError("Application not found")
    stored_records = await store.list_rows("invoice_records", {"application_id": application_id})
    records = [row for row in stored_records if is_client_validation_record(row)]
    approved_count = sum(row.get("review_status") in APPROVED_REVIEW_STATUSES for row in records)
    rejected_count = sum(row.get("review_status") == "rejected" for row in records)
    pending_count = sum(row.get("review_status") not in REVIEWED_REVIEW_STATUSES for row in records)
    if records and pending_count == 0 and approved_count:
        return await run_application_validation(
            store,
            application_id=application_id,
            firm_id=firm_id,
        )

    await store.update_row("applications", application_id, {"status": "extraction_review"})
    return ValidationWorkflowResult(
        current_stage="extraction_review",
        validation_ran=False,
        record_count=len(records),
        approved_record_count=approved_count,
        rejected_record_count=rejected_count,
        pending_record_count=pending_count,
        eligible_record_count=approved_count,
    )
