from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.config import Settings, get_settings
from app.dependencies import current_user, require_firm_row, require_roles
from app.repositories import DataStore, get_store
from app.schemas.auth import UserContext
from app.schemas.compliance import FindingResolution, ReturnToPreparer
from app.services.audit import record_audit
from app.services.readiness import build_readiness_summary
from app.services.reconciliation import ReconciliationRecord, reconcile_records
from app.services.reports import generate_invoice_csv, generate_readiness_pdf, generate_reconciliation_csv
from app.services.validation import InvoiceInput, detect_duplicate_groups, validate_invoice

router = APIRouter(tags=["compliance"])


def _date(value: Any) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _reconciliation_record(row: dict[str, Any]) -> ReconciliationRecord:
    return ReconciliationRecord(
        record_id=row["id"],
        supplier_gstin=row.get("supplier_gstin") or "",
        invoice_number=row.get("invoice_number") or "",
        invoice_date=_date(row["invoice_date"]),
        taxable_value=_decimal(row.get("taxable_value")),
        cgst=_decimal(row.get("cgst")),
        sgst=_decimal(row.get("sgst")),
        igst=_decimal(row.get("igst")),
        cess=_decimal(row.get("cess")),
    )


@router.post("/applications/{application_id}/validate")
async def validate_application(
    application_id: str,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    client = await store.get_row("clients", application["client_id"])
    assert client is not None
    records = await store.list_rows("invoice_records", {"application_id": application_id})
    old = await store.list_rows("validation_findings", {"application_id": application_id})
    for row in old:
        await store.delete_row("validation_findings", row["id"])

    inserted: list[dict[str, Any]] = []
    inputs: list[InvoiceInput] = []
    record_map: dict[str, dict[str, Any]] = {}
    for row in records:
        invoice = InvoiceInput(
            supplier_name=row.get("supplier_name"),
            supplier_gstin=row.get("supplier_gstin"),
            customer_name=row.get("customer_name"),
            customer_gstin=row.get("customer_gstin"),
            invoice_number=row.get("invoice_number"),
            invoice_date=_date(row["invoice_date"]) if row.get("invoice_date") else None,
            taxable_value=row.get("taxable_value"),
            cgst=row.get("cgst"),
            sgst=row.get("sgst"),
            igst=row.get("igst"),
            cess=row.get("cess"),
            invoice_total=row.get("invoice_total"),
            metadata={"record_id": row["id"]},
        )
        inputs.append(invoice)
        record_map[row["id"]] = row
        expected = client.get("gstin") if row.get("invoice_category") == "sales" else None
        for finding in validate_invoice(
            invoice,
            period_start=_date(application["period_start"]),
            period_end=_date(application["period_end"]),
            expected_customer_gstin=expected,
        ):
            inserted.append(await store.insert_row("validation_findings", {
                "firm_id": user.firm_id,
                "application_id": application_id,
                "document_id": row.get("document_id"),
                "invoice_record_id": row["id"],
                "finding_type": finding.finding_type,
                "severity": finding.severity,
                "message": finding.message,
                "details": finding.details,
                "status": "open",
            }))

    for group in detect_duplicate_groups(inputs):
        ids = [item.metadata["record_id"] for item in group]
        inserted.append(await store.insert_row("validation_findings", {
            "firm_id": user.firm_id,
            "application_id": application_id,
            "document_id": record_map[ids[0]].get("document_id"),
            "invoice_record_id": ids[0],
            "finding_type": "duplicate_invoice",
            "severity": "medium",
            "message": "A possible duplicate invoice was detected.",
            "details": {"invoice_record_ids": ids},
            "status": "open",
        }))
    await store.update_row("applications", application_id, {"status": "validation_review"})
    return {"finding_count": len(inserted), "findings": inserted}


@router.get("/applications/{application_id}/findings")
async def list_findings(
    application_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> list[dict]:
    await require_firm_row(store, "applications", application_id, user.firm_id)
    return await store.list_rows("validation_findings", {"application_id": application_id}, order="created_at", desc=True)


@router.post("/findings/{finding_id}/resolve")
async def resolve_finding(
    finding_id: str,
    payload: FindingResolution,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    finding = await store.get_row("validation_findings", finding_id)
    if not finding or finding.get("firm_id") != user.firm_id:
        raise HTTPException(status_code=404, detail="Finding not found")
    updated = await store.update_row("validation_findings", finding_id, {
        "status": payload.status,
        "resolved_by": user.user_id,
        "resolved_at": datetime.now(UTC).isoformat(),
    })
    assert updated is not None
    return updated


@router.post("/applications/{application_id}/reconcile")
async def run_reconciliation(
    application_id: str,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    rows = await store.list_rows("invoice_records", {"application_id": application_id})
    purchase = [_reconciliation_record(row) for row in rows if row.get("invoice_category") == "purchase"]
    gstr2b = [_reconciliation_record(row) for row in rows if row.get("invoice_category") == "gstr2b"]
    result = reconcile_records(purchase, gstr2b)
    run = await store.insert_row("reconciliation_runs", {
        "firm_id": user.firm_id,
        "application_id": application_id,
        "status": "completed",
        "summary": result.summary,
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "created_by": user.user_id,
    })
    persisted_items: list[dict[str, Any]] = []
    for item in result.items:
        persisted_items.append(await store.insert_row("reconciliation_items", {
            "reconciliation_run_id": run["id"],
            "purchase_invoice_id": item.purchase_record.record_id if item.purchase_record else None,
            "gstr2b_invoice_id": item.gstr2b_record.record_id if item.gstr2b_record else None,
            "match_status": item.match_status,
            "match_score": item.match_score,
            "differences": item.differences,
        }))
    await store.update_row("applications", application_id, {"status": "reconciliation_review"})
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="reconciliation.completed",
        entity_type="reconciliation_run",
        entity_id=run["id"],
        client_id=application["client_id"],
        application_id=application_id,
        after_data=result.summary,
    )
    return {**run, "items": persisted_items}


@router.get("/applications/{application_id}/reconciliation")
async def get_reconciliation(
    application_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    await require_firm_row(store, "applications", application_id, user.firm_id)
    runs = await store.list_rows("reconciliation_runs", {"application_id": application_id}, order="created_at", desc=True, limit=1)
    if not runs:
        return {"summary": {}, "items": []}
    items = await store.list_rows("reconciliation_items", {"reconciliation_run_id": runs[0]["id"]})
    return {**runs[0], "items": items}


@router.get("/applications/{application_id}/readiness-summary")
async def readiness_summary(
    application_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    client = await store.get_row("clients", application["client_id"])
    assert client is not None
    return await build_readiness_summary(store, application=application, client=client)


@router.post("/applications/{application_id}/export")
async def export_application(
    application_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    client = await store.get_row("clients", application["client_id"])
    assert client is not None
    summary = await build_readiness_summary(store, application=application, client=client)
    invoices = await store.list_rows("invoice_records", {"application_id": application_id})
    reconciliation = await get_reconciliation(application_id, user, store)
    files = {
        "readiness_pdf": ("readiness-report.pdf", generate_readiness_pdf(summary), "application/pdf"),
        "invoice_csv": ("extracted-invoices.csv", generate_invoice_csv(invoices), "text/csv"),
        "reconciliation_csv": ("gstr2b-reconciliation.csv", generate_reconciliation_csv(reconciliation.get("items", [])), "text/csv"),
    }
    output: dict[str, str] = {}
    for key, (filename, content, mime_type) in files.items():
        path = f"{user.firm_id}/{client['id']}/{application_id}/{filename}"
        await store.upload_file(settings.supabase_exports_bucket, path, content, mime_type)
        output[key] = await store.create_signed_url(settings.supabase_exports_bucket, path, 1800)
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="application.exported",
        entity_type="application",
        entity_id=application_id,
        client_id=client["id"],
        application_id=application_id,
        after_data={"files": list(output)},
    )
    return output


@router.post("/applications/{application_id}/approve")
async def approve_application(
    application_id: str,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    await require_firm_row(store, "applications", application_id, user.firm_id)
    updated = await store.update_row("applications", application_id, {"status": "ready_for_filing"})
    assert updated is not None
    return updated


@router.post("/applications/{application_id}/return")
async def return_to_preparer(
    application_id: str,
    payload: ReturnToPreparer,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    updated = await store.update_row("applications", application_id, {"status": "extraction_review", "final_notes": payload.notes})
    assert updated is not None
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="application.returned_to_preparer",
        entity_type="application",
        entity_id=application_id,
        client_id=application["client_id"],
        application_id=application_id,
        after_data={"notes": payload.notes},
    )
    return updated


async def _store_evidence(
    store: DataStore,
    settings: Settings,
    *,
    application: dict[str, Any],
    client: dict[str, Any],
    file: UploadFile,
    document_type: str,
    user_id: str,
) -> dict[str, Any]:
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Evidence file is too large")
    digest = hashlib.sha256(content).hexdigest()
    safe = "".join(char if char.isalnum() or char in ".-_" else "_" for char in (file.filename or document_type))
    path = f"{application['firm_id']}/{client['id']}/{application['id']}/filing/{digest[:12]}-{safe}"
    await store.upload_file(settings.supabase_documents_bucket, path, content, file.content_type or "application/octet-stream")
    return await store.insert_row("documents", {
        "firm_id": application["firm_id"],
        "client_id": client["id"],
        "application_id": application["id"],
        "requirement_id": None,
        "source": "filing_evidence",
        "original_name": file.filename or safe,
        "mime_type": file.content_type or "application/octet-stream",
        "storage_path": path,
        "file_size": len(content),
        "sha256": digest,
        "document_type": document_type,
        "processing_status": "approved",
        "uploaded_by_user_id": user_id,
        "uploaded_from_phone": None,
    })


@router.post("/applications/{application_id}/filing-evidence")
async def record_filing_evidence(
    application_id: str,
    filing_date: date = Form(...),
    arn: str = Form(...),
    final_notes: str | None = Form(None),
    filed_return: UploadFile | None = File(None),
    payment_challan: UploadFile | None = File(None),
    user: UserContext = Depends(require_roles("firm_admin", "reviewer")),
    store: DataStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    client = await store.get_row("clients", application["client_id"])
    assert client is not None
    update: dict[str, Any] = {
        "filing_date": filing_date.isoformat(),
        "arn": arn,
        "final_notes": final_notes,
        "status": "completed",
    }
    if filed_return:
        document = await _store_evidence(store, settings, application=application, client=client, file=filed_return, document_type="filed_return", user_id=user.user_id)
        update["filed_return_document_id"] = document["id"]
    if payment_challan:
        document = await _store_evidence(store, settings, application=application, client=client, file=payment_challan, document_type="payment_challan", user_id=user.user_id)
        update["payment_challan_document_id"] = document["id"]
    updated = await store.update_row("applications", application_id, update)
    assert updated is not None
    return updated
