"""Live application workflow progress derived from persisted application evidence."""

from __future__ import annotations

from typing import Any

from app.repositories.base import DataStore
from app.services.document_collection import get_document_collection_status
from app.services.validation_workflow import (
    REVIEWED_REVIEW_STATUSES,
    is_client_validation_record,
)

REVIEWED_VALIDATION_STATUSES = frozenset({"resolved", "accepted"})
REVIEWED_RECONCILIATION_STATUSES = frozenset({"reviewed", "resolved"})


async def get_workflow_progress(store: DataStore, application_id: str) -> dict[str, Any]:
    application = await store.get_row("applications", application_id)
    if not application:
        raise ValueError("Application not found")
    collection = await get_document_collection_status(store, application_id)
    stored_records = await store.list_rows("invoice_records", {"application_id": application_id})
    records = [row for row in stored_records if is_client_validation_record(row)]
    client_record_ids = {str(row["id"]) for row in records}
    stored_findings = await store.list_rows(
        "validation_findings", {"application_id": application_id}
    )
    findings = [
        row
        for row in stored_findings
        if not row.get("invoice_record_id")
        or str(row.get("invoice_record_id")) in client_record_ids
    ]
    runs = await store.list_rows(
        "reconciliation_runs",
        {"application_id": application_id},
        order="created_at",
        desc=True,
    )
    reconciliation_items: list[dict[str, Any]] = []
    for run in runs[:1]:
        reconciliation_items.extend(
            await store.list_rows("reconciliation_items", {"reconciliation_run_id": run["id"]})
        )

    record_count = len(records)
    reviewed_count = sum(row.get("review_status") in REVIEWED_REVIEW_STATUSES for row in records)
    approved_count = sum(
        row.get("review_status") in {"approved", "edited_and_approved"} for row in records
    )
    rejected_count = sum(row.get("review_status") == "rejected" for row in records)
    reviewed_findings = sum(row.get("status") in REVIEWED_VALIDATION_STATUSES for row in findings)
    open_findings = len(findings) - reviewed_findings
    review_required_items = [
        row for row in reconciliation_items if row.get("match_status") != "exact_match"
    ]
    reviewed_reconciliation = sum(
        row.get("review_status") in REVIEWED_RECONCILIATION_STATUSES
        for row in review_required_items
    )
    open_reconciliation = len(review_required_items) - reviewed_reconciliation

    requested_ratio = 1.0 if collection["workflow_status"] != "not_started" else 0.0
    collection_ratio = collection["progress_percent"] / 100
    extraction_ratio = reviewed_count / record_count if record_count else 0.0
    validation_started = str(application.get("status")) in {
        "validation_review",
        "reconciliation_review",
        "ready_for_ca_review",
        "ready_for_filing",
    } or bool(findings)
    validation_ratio = (
        (reviewed_findings / len(findings) if findings else 1.0) if validation_started else 0.0
    )
    reconciliation_started = bool(runs)
    latest_run_completed = bool(runs) and runs[0].get("status") == "completed"
    reconciliation_ratio = (
        reviewed_reconciliation / len(review_required_items)
        if review_required_items
        else (1.0 if latest_run_completed else 0.0)
    )
    ready_for_filing = validation_ratio >= 1

    if validation_started and not ready_for_filing:
        current_stage = "validation_review"
    elif ready_for_filing and reconciliation_ratio < 1:
        current_stage = "reconciliation_review"
    elif ready_for_filing:
        current_stage = "ready_for_filing"
    elif record_count or str(application.get("status")) == "extraction_review":
        current_stage = "extraction_review"
    elif collection_ratio == 1:
        current_stage = "documents_received"
    elif collection_ratio:
        current_stage = "partially_received"
    else:
        current_stage = "documents_requested" if requested_ratio else "not_started"

    step_data = [
        ("documents_requested", "Documents Requested", requested_ratio),
        ("documents_received", "Documents Received", collection_ratio),
        ("extraction_review", "Extraction Review", extraction_ratio),
        ("validation_review", "Validation Review", validation_ratio),
        ("reconciliation_review", "Reconciliation Review", reconciliation_ratio),
        ("ready_for_filing", "Ready for Filing", 1.0 if ready_for_filing else 0.0),
    ]
    current_index = next(
        (index for index, (key, _, _) in enumerate(step_data) if key == current_stage),
        0,
    )
    steps = []
    for index, (key, label, ratio) in enumerate(step_data):
        if key == "reconciliation_review" and not ready_for_filing:
            state = "pending"
        elif ratio >= 1:
            state = "completed"
        elif key == current_stage:
            state = "current"
        elif index < current_index and ratio >= 1:
            state = "completed"
        else:
            state = "pending"
        steps.append(
            {
                "key": key,
                "label": label,
                "state": state,
                "progress_percent": round(ratio * 100),
            }
        )
    return {
        "application_id": application_id,
        "application_status": application.get("status"),
        "current_stage": current_stage,
        "progress_percent": round(
            100
            * sum(
                (
                    requested_ratio,
                    collection_ratio,
                    extraction_ratio,
                    validation_ratio,
                )
            )
            / 4
        ),
        "steps": steps,
        "collection": collection,
        "extraction": {
            "record_count": record_count,
            "reviewed_count": reviewed_count,
            "approved_count": approved_count,
            "rejected_count": rejected_count,
            "pending_count": record_count - reviewed_count,
            "progress_percent": round(extraction_ratio * 100),
        },
        "validation": {
            "finding_count": len(findings),
            "open_count": open_findings,
            "reviewed_count": reviewed_findings,
            "progress_percent": round(validation_ratio * 100),
        },
        "reconciliation": {
            "run_count": len(runs),
            "item_count": len(reconciliation_items),
            "open_count": open_reconciliation,
            "review_required_count": len(review_required_items),
            "reviewed_count": reviewed_reconciliation,
            "progress_percent": round(reconciliation_ratio * 100),
            "available": ready_for_filing,
            "status": (
                "complete"
                if latest_run_completed and reconciliation_ratio >= 1
                else "in_progress"
                if reconciliation_started
                else "not_started"
            ),
            "export_enabled": latest_run_completed and reconciliation_ratio >= 1,
        },
        "readiness": {
            "ready_for_filing": ready_for_filing,
            "ready_for_filing_percent": 100 if ready_for_filing else 0,
            "main_export_enabled": ready_for_filing,
        },
    }


async def sync_ready_for_filing_state(
    store: DataStore,
    application_id: str,
) -> tuple[dict[str, Any], bool]:
    """Synchronize the legacy application status without making it the readiness authority."""
    progress = await get_workflow_progress(store, application_id)
    application = await store.get_row("applications", application_id)
    if not application:
        raise ValueError("Application not found")
    ready = bool(progress["readiness"]["ready_for_filing"])
    current = str(application.get("status") or "")
    changed_to_ready = ready and current != "ready_for_filing"
    if changed_to_ready:
        await store.update_row("applications", application_id, {"status": "ready_for_filing"})
        progress["application_status"] = "ready_for_filing"
    elif not ready and current == "ready_for_filing":
        await store.update_row("applications", application_id, {"status": "validation_review"})
        progress["application_status"] = "validation_review"
    return progress, changed_to_ready
