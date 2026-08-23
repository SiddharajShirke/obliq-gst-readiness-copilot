from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from app.api.v1.alerts import generate_and_store_explanation
from app.config import Settings, get_settings
from app.dependencies import current_user, require_firm_row, require_roles
from app.repositories import DataStore, get_store
from app.schemas.auth import UserContext
from app.schemas.compliance import (
    BulkFindingResolution,
    BulkReconciliationReview,
    FindingResolution,
    ReturnToPreparer,
    ValidationCorrectionRequest,
)
from app.services.alert_explanations import build_alert_evidence
from app.services.audit import record_audit
from app.services.document_processing.pipeline import ingest_document, process_ingested_document
from app.services.readiness import build_readiness_summary
from app.services.reconciliation import ReconciliationRecord, reconcile_records
from app.services.reports import (
    generate_document_manifest_csv,
    generate_export_archive,
    generate_invoice_csv,
    generate_readiness_pdf,
    generate_reconciliation_csv,
    generate_reconciliation_pdf,
    generate_validation_csv,
)
from app.services.secure_upload import (
    ResolvedUploadContext,
    SecureUploadValidationError,
)
from app.services.validation_corrections import (
    apply_correction_proposal,
    create_correction_proposal,
)
from app.services.validation_portfolio import get_validation_portfolio
from app.services.validation_workflow import run_application_validation
from app.services.workflow_progress import (
    get_workflow_progress,
    sync_ready_for_filing_state,
)

router = APIRouter(tags=["compliance"])


async def _sync_and_audit_readiness(
    store: DataStore,
    *,
    application: dict[str, Any],
    user: UserContext,
) -> dict[str, Any]:
    progress, changed_to_ready = await sync_ready_for_filing_state(store, str(application["id"]))
    if changed_to_ready:
        for action in ("validation_review_completed", "ready_for_filing_reached"):
            await record_audit(
                store,
                firm_id=user.firm_id,
                user_id=user.user_id,
                action=action,
                entity_type="application",
                entity_id=str(application["id"]),
                client_id=application["client_id"],
                application_id=str(application["id"]),
                after_data={
                    "validation_review_percent": 100,
                    "ready_for_filing": True,
                },
            )
    return progress


def _alert_type(item: dict[str, Any]) -> str:
    status_value = str(item.get("match_status") or "").lower()
    flags = {str(value).lower() for value in item.get("special_flags") or []}
    if "itc_not_available" in flags:
        return "ITC_NOT_AVAILABLE"
    if "rcm" in flags:
        return "RCM"
    if status_value == "invoice_number_mismatch":
        return "INVOICE_NUMBER_MISMATCH"
    if status_value == "books_only":
        return "BOOKS_ONLY"
    if status_value == "gstr2b_only":
        return "GSTR2B_ONLY"
    if status_value == "ambiguous_match":
        return "AMBIGUOUS_MATCH"
    if status_value == "duplicate":
        return "DUPLICATE"
    difference_fields = set((item.get("evidence") or {}).get("difference_fields") or [])
    if difference_fields == {"taxable_value"}:
        return "TAXABLE_VALUE_MISMATCH"
    if difference_fields & {"igst", "cgst", "sgst", "cess", "total_tax"}:
        return "TAX_MISMATCH"
    if status_value == "value_mismatch":
        return "VALUE_MISMATCH"
    return "OTHER_RECONCILIATION_REVIEW"


@router.post(
    "/reconciliation/items/{item_id}/raise-alert",
    status_code=status.HTTP_201_CREATED,
)
async def raise_reconciliation_alert(
    item_id: str,
    background_tasks: BackgroundTasks,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    item = await store.get_row("reconciliation_items", item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Reconciliation item not found")
    run = await store.get_row("reconciliation_runs", item["reconciliation_run_id"])
    if not run or run.get("firm_id") != user.firm_id:
        raise HTTPException(status_code=404, detail="Reconciliation item not found")
    existing = await store.list_rows("alerts", {"reconciliation_item_id": item_id}, limit=1)
    if existing:
        return existing[0]
    application = await require_firm_row(store, "applications", run["application_id"], user.firm_id)
    client = await store.get_row("clients", application["client_id"])
    assert client is not None
    alert_type = _alert_type(item)
    evidence = build_alert_evidence(
        alert_type=alert_type,
        client_name=client["business_name"],
        tax_period=application["period_label"],
        reconciliation_evidence=item.get("evidence") or {},
    )
    invoice_number = (
        ((item.get("evidence") or {}).get("books") or {}).get("invoice_number")
        or ((item.get("evidence") or {}).get("gstr2b") or {}).get("invoice_number")
        or "GST record"
    )
    alert = await store.insert_row(
        "alerts",
        {
            "firm_id": user.firm_id,
            "application_id": application["id"],
            "client_id": application["client_id"],
            "reconciliation_item_id": item_id,
            "alert_type": alert_type,
            "title": alert_type.replace("_", " ").title(),
            "message": f"{invoice_number} requires CA review.",
            "severity": "medium",
            "status": "open",
            "evidence": evidence,
            "ai_explanation": None,
            "ai_explanation_status": "pending",
        },
    )
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="reconciliation_alert_raised",
        entity_type="alert",
        entity_id=alert["id"],
        client_id=application["client_id"],
        application_id=application["id"],
        metadata={"reconciliation_item_id": item_id, "alert_type": alert_type},
    )
    background_tasks.add_task(
        generate_and_store_explanation,
        store,
        settings,
        alert_id=alert["id"],
        firm_id=user.firm_id,
        user_id=user.user_id,
    )
    return alert


def _date(value: Any) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _optional_decimal(value: Any) -> Decimal | None:
    return None if value in (None, "") else Decimal(str(value))


def _reconciliation_record(row: dict[str, Any]) -> ReconciliationRecord:
    return ReconciliationRecord(
        record_id=row["id"],
        supplier_gstin=row.get("supplier_gstin") or "",
        invoice_number=row.get("invoice_number") or "",
        invoice_date=_date(row["invoice_date"]),
        taxable_value=_optional_decimal(row.get("taxable_value")),
        cgst=_optional_decimal(row.get("cgst")),
        sgst=_optional_decimal(row.get("sgst")),
        igst=_optional_decimal(row.get("igst")),
        cess=_optional_decimal(row.get("cess")),
        total_document_value=_optional_decimal(row.get("invoice_total")),
        itc_status=row.get("itc_status"),
        rcm_flag=row.get("rcm_flag"),
        transaction_type=row.get("transaction_type"),
    )


@router.post("/applications/{application_id}/reconciliation/gstr2b", status_code=201)
async def upload_gstr2b(
    application_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: UserContext = Depends(require_roles("firm_admin", "gst_preparer", "reviewer")),
    store: DataStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    client = await store.get_row("clients", application["client_id"])
    firm = await store.get_row("firms", user.firm_id)
    assert client is not None and firm is not None
    checklist = await store.list_rows("document_requirements", {"application_id": application_id})
    context = ResolvedUploadContext({}, firm, client, application, None, checklist)
    try:
        document = await ingest_document(
            store,
            settings,
            context=context,
            filename=file.filename or "gstr2b.json",
            declared_mime_type=file.content_type or "application/octet-stream",
            content=await file.read(settings.max_upload_mb * 1024 * 1024 + 1),
        )
    except SecureUploadValidationError as exc:
        raise HTTPException(
            status_code=409 if exc.code == "duplicate" else 400, detail=str(exc)
        ) from exc
    if document.get("document_type") != "gstr2b":
        raise HTTPException(status_code=400, detail="The uploaded file is not GSTR-2B")
    background_tasks.add_task(process_ingested_document, store, settings, document["id"])
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="gstr2b_uploaded",
        entity_type="document",
        entity_id=document["id"],
        client_id=application["client_id"],
        application_id=application_id,
    )
    return document


@router.get("/applications/{application_id}/reconciliation/gstr2b")
async def get_gstr2b_status(
    application_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict[str, Any]:
    await require_firm_row(store, "applications", application_id, user.firm_id)
    rows = await store.list_rows(
        "documents",
        {"application_id": application_id, "document_type": "gstr2b"},
        order="created_at",
        desc=True,
        limit=1,
    )
    if not rows:
        return {"status": "not_uploaded", "document": None}
    document = rows[0]
    ready = document.get("processing_status") in {"ready_for_review", "needs_review", "approved"}
    return {
        "status": "ready_to_reconcile" if ready else document.get("processing_status"),
        "document": document,
    }


@router.post("/applications/{application_id}/validate")
async def validate_application(
    application_id: str,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    result = await run_application_validation(
        store,
        application_id=application_id,
        firm_id=user.firm_id,
    )
    workflow = await _sync_and_audit_readiness(store, application=application, user=user)
    return {**result.as_dict(), "workflow": workflow}


@router.get("/applications/{application_id}/findings")
async def list_findings(
    application_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> list[dict]:
    await require_firm_row(store, "applications", application_id, user.firm_id)
    return await store.list_rows(
        "validation_findings", {"application_id": application_id}, order="created_at", desc=True
    )


@router.get("/applications/{application_id}/validation-portfolio")
async def validation_portfolio(
    application_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict[str, Any]:
    await require_firm_row(store, "applications", application_id, user.firm_id)
    return await get_validation_portfolio(store, application_id)


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
    updated = await store.update_row(
        "validation_findings",
        finding_id,
        {
            "status": payload.status,
            "resolved_by": user.user_id,
            "resolved_at": datetime.now(UTC).isoformat(),
        },
    )
    assert updated is not None
    application = await require_firm_row(
        store, "applications", str(finding["application_id"]), user.firm_id
    )
    workflow = await _sync_and_audit_readiness(store, application=application, user=user)
    return {**updated, "workflow": workflow}


@router.post("/applications/{application_id}/findings/bulk-review")
async def bulk_review_findings(
    application_id: str,
    payload: BulkFindingResolution,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict[str, Any]:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    requested_ids = list(dict.fromkeys(payload.finding_ids))
    findings = [
        await store.get_row("validation_findings", finding_id) for finding_id in requested_ids
    ]
    if any(
        finding is None
        or str(finding.get("application_id")) != str(application_id)
        or str(finding.get("firm_id")) != str(user.firm_id)
        for finding in findings
    ):
        raise HTTPException(
            status_code=404, detail="One or more validation findings were not found"
        )
    typed_findings = [finding for finding in findings if finding is not None]
    if any(finding.get("status") != "open" for finding in typed_findings):
        raise HTTPException(status_code=409, detail="Only open validation findings are eligible")
    now = datetime.now(UTC).isoformat()
    for finding in typed_findings:
        await store.update_row(
            "validation_findings",
            str(finding["id"]),
            {"status": payload.status, "resolved_by": user.user_id, "resolved_at": now},
        )
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="bulk_validation_review",
        entity_type="application",
        entity_id=application_id,
        client_id=application["client_id"],
        application_id=application_id,
        metadata={"finding_count": len(typed_findings), "status": payload.status},
    )
    workflow = await _sync_and_audit_readiness(store, application=application, user=user)
    return {"updated_count": len(typed_findings), "status": payload.status, "workflow": workflow}


@router.post("/findings/{finding_id}/raise-alert", status_code=status.HTTP_201_CREATED)
async def raise_validation_alert(
    finding_id: str,
    background_tasks: BackgroundTasks,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    finding = await store.get_row("validation_findings", finding_id)
    if not finding or str(finding.get("firm_id")) != str(user.firm_id):
        raise HTTPException(status_code=404, detail="Validation finding not found")
    existing = await store.list_rows("alerts", {"validation_finding_id": finding_id}, limit=1)
    if existing:
        return existing[0]
    application = await require_firm_row(
        store, "applications", finding["application_id"], user.firm_id
    )
    client = await store.get_row("clients", application["client_id"])
    record = (
        await store.get_row("invoice_records", finding["invoice_record_id"])
        if finding.get("invoice_record_id")
        else None
    )
    alert_type = str(finding.get("finding_type") or "validation_review").upper()
    detail_fields = [str(key) for key in (finding.get("details") or {}).keys()]
    evidence = build_alert_evidence(
        alert_type=alert_type,
        client_name=(client or {}).get("business_name") or "Client",
        tax_period=application.get("period_label") or "GST period",
        reconciliation_evidence={
            "books": record,
            "gstr2b": None,
            "difference_fields": detail_fields,
        },
    )
    alert = await store.insert_row(
        "alerts",
        {
            "firm_id": user.firm_id,
            "application_id": application["id"],
            "client_id": application["client_id"],
            "validation_finding_id": finding_id,
            "reconciliation_item_id": None,
            "workflow_area": "validation",
            "alert_category": alert_type,
            "alert_type": alert_type,
            "title": alert_type.replace("_", " ").title(),
            "message": finding.get("message") or "Validation evidence requires CA review.",
            "severity": finding.get("severity") or "medium",
            "status": "open",
            "evidence": evidence,
            "ai_explanation": None,
            "ai_explanation_status": "pending",
        },
    )
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="validation_alert_raised",
        entity_type="alert",
        entity_id=alert["id"],
        client_id=application["client_id"],
        application_id=application["id"],
        metadata={"validation_finding_id": finding_id, "alert_type": alert_type},
    )
    background_tasks.add_task(
        generate_and_store_explanation,
        store,
        settings,
        alert_id=alert["id"],
        firm_id=user.firm_id,
        user_id=user.user_id,
    )
    return alert


@router.post("/applications/{application_id}/validation-corrections/proposals", status_code=201)
async def propose_validation_correction(
    application_id: str,
    payload: ValidationCorrectionRequest,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    if payload.mode == "manual" and not payload.changes:
        raise HTTPException(status_code=422, detail="Manual corrections require at least one field")
    try:
        proposal = await create_correction_proposal(
            store,
            settings,
            application=application,
            user_id=user.user_id,
            record_ids=list(dict.fromkeys(payload.record_ids)),
            mode=payload.mode,
            manual_changes=payload.changes,
            rationale=payload.rationale,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="validation_correction_proposed",
        entity_type="validation_correction_proposal",
        entity_id=proposal["id"],
        client_id=application["client_id"],
        application_id=application_id,
        metadata={"proposal_type": payload.mode, "record_count": len(payload.record_ids)},
    )
    return proposal


async def _require_correction_proposal(
    store: DataStore, proposal_id: str, firm_id: str
) -> dict[str, Any]:
    proposal = await store.get_row("validation_correction_proposals", proposal_id)
    if not proposal or str(proposal.get("firm_id")) != str(firm_id):
        raise HTTPException(status_code=404, detail="Correction proposal not found")
    return proposal


@router.post("/validation-corrections/{proposal_id}/apply")
async def apply_validation_correction(
    proposal_id: str,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict[str, Any]:
    proposal = await _require_correction_proposal(store, proposal_id, user.firm_id)
    try:
        updated = await apply_correction_proposal(store, proposal, user_id=user.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="validation_correction_applied",
        entity_type="validation_correction_proposal",
        entity_id=proposal_id,
        client_id=proposal.get("client_id"),
        application_id=proposal.get("application_id"),
        before_data={"status": "proposed"},
        after_data={"status": "applied", "changes": proposal.get("changes") or []},
    )
    # Corrections are proposals until the CA applies them. Once accepted, rebuild the
    # deterministic findings from approved records so the Validation tab never shows
    # stale evidence. This remains local/background-free deterministic work.
    revalidation = await validate_application(str(proposal["application_id"]), user, store)
    return {**updated, "revalidation": revalidation}


@router.post("/validation-corrections/{proposal_id}/reject")
async def reject_validation_correction(
    proposal_id: str,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict[str, Any]:
    proposal = await _require_correction_proposal(store, proposal_id, user.firm_id)
    if proposal.get("status") != "proposed":
        raise HTTPException(status_code=409, detail="Correction proposal has already been decided")
    updated = await store.update_row(
        "validation_correction_proposals",
        proposal_id,
        {
            "status": "rejected",
            "decided_by": user.user_id,
            "decided_at": datetime.now(UTC).isoformat(),
        },
    )
    assert updated is not None
    return updated


@router.post("/applications/{application_id}/reconcile")
async def run_reconciliation(
    application_id: str,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    readiness = await get_workflow_progress(store, application_id)
    if not readiness["reconciliation"]["available"]:
        raise HTTPException(
            status_code=409,
            detail="Complete Validation Review before starting GSTR-2B reconciliation",
        )
    rows = await store.list_rows("invoice_records", {"application_id": application_id})
    usable = [
        row
        for row in rows
        if row.get("supplier_gstin") and row.get("invoice_number") and row.get("invoice_date")
    ]
    purchase = [
        _reconciliation_record(row) for row in usable if row.get("invoice_category") == "purchase"
    ]
    gstr2b = [
        _reconciliation_record(row) for row in usable if row.get("invoice_category") == "gstr2b"
    ]
    if not gstr2b:
        raise HTTPException(status_code=409, detail="GSTR-2B is not ready to reconcile")
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="reconciliation_started",
        entity_type="application",
        entity_id=application_id,
        client_id=application["client_id"],
        application_id=application_id,
    )
    result = reconcile_records(purchase, gstr2b)
    run = await store.insert_row(
        "reconciliation_runs",
        {
            "firm_id": user.firm_id,
            "application_id": application_id,
            "status": "completed",
            "summary": result.summary,
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
            "created_by": user.user_id,
        },
    )
    persisted_items: list[dict[str, Any]] = []
    for item in result.items:
        persisted_items.append(
            await store.insert_row(
                "reconciliation_items",
                {
                    "reconciliation_run_id": run["id"],
                    "purchase_invoice_id": item.purchase_record.record_id
                    if item.purchase_record
                    else None,
                    "gstr2b_invoice_id": item.gstr2b_record.record_id
                    if item.gstr2b_record
                    else None,
                    "match_status": item.match_status,
                    "match_score": str(item.match_score),
                    "differences": item.differences,
                    "evidence": item.evidence,
                    "special_flags": item.special_flags,
                    "review_status": "pending",
                },
            )
        )
    await _sync_and_audit_readiness(store, application=application, user=user)
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="reconciliation_completed",
        entity_type="reconciliation_run",
        entity_id=run["id"],
        client_id=application["client_id"],
        application_id=application_id,
        after_data=result.summary,
    )
    return {**run, "items": persisted_items}


@router.post("/reconciliation/items/{item_id}/review")
async def review_reconciliation_item(
    item_id: str,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict[str, Any]:
    item = await store.get_row("reconciliation_items", item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Reconciliation item not found")
    run = await store.get_row("reconciliation_runs", item["reconciliation_run_id"])
    if not run or run.get("firm_id") != user.firm_id:
        raise HTTPException(status_code=404, detail="Reconciliation item not found")
    now = datetime.now(UTC).isoformat()
    updated = await store.update_row(
        "reconciliation_items",
        item_id,
        {"review_status": "reviewed", "reviewed_by": user.user_id, "reviewed_at": now},
    )
    assert updated is not None
    application = await store.get_row("applications", run["application_id"])
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="reconciliation_item_reviewed",
        entity_type="reconciliation_item",
        entity_id=item_id,
        client_id=(application or {}).get("client_id"),
        application_id=run["application_id"],
    )
    workflow = await get_workflow_progress(store, str(run["application_id"]))
    if workflow["reconciliation"]["export_enabled"]:
        await record_audit(
            store,
            firm_id=user.firm_id,
            user_id=user.user_id,
            action="reconciliation_review_completed",
            entity_type="reconciliation_run",
            entity_id=str(run["id"]),
            client_id=(application or {}).get("client_id"),
            application_id=str(run["application_id"]),
            after_data={"reconciliation_review_percent": 100},
        )
    return updated


@router.post("/applications/{application_id}/reconciliation/items/bulk-review")
async def bulk_review_reconciliation_items(
    application_id: str,
    payload: BulkReconciliationReview,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict[str, Any]:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    runs = await store.list_rows(
        "reconciliation_runs",
        {"application_id": application_id},
        order="created_at",
        desc=True,
        limit=1,
    )
    if not runs:
        raise HTTPException(status_code=409, detail="Run reconciliation before reviewing findings")
    latest_run = runs[0]
    requested_ids = list(dict.fromkeys(payload.item_ids))
    items = [await store.get_row("reconciliation_items", item_id) for item_id in requested_ids]
    if any(
        item is None or str(item.get("reconciliation_run_id")) != str(latest_run["id"])
        for item in items
    ):
        raise HTTPException(
            status_code=404, detail="One or more reconciliation findings were not found"
        )
    typed_items = [item for item in items if item is not None]
    if any(
        item.get("match_status") == "exact_match"
        or item.get("review_status") in {"reviewed", "resolved"}
        for item in typed_items
    ):
        raise HTTPException(
            status_code=409,
            detail="Only pending findings requiring CA review are eligible",
        )
    now = datetime.now(UTC).isoformat()
    for item in typed_items:
        await store.update_row(
            "reconciliation_items",
            str(item["id"]),
            {"review_status": "reviewed", "reviewed_by": user.user_id, "reviewed_at": now},
        )
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="bulk_reconciliation_review",
        entity_type="reconciliation_run",
        entity_id=str(latest_run["id"]),
        client_id=application["client_id"],
        application_id=application_id,
        metadata={"item_count": len(typed_items), "action": payload.action},
    )
    workflow = await get_workflow_progress(store, application_id)
    if workflow["reconciliation"]["export_enabled"]:
        await record_audit(
            store,
            firm_id=user.firm_id,
            user_id=user.user_id,
            action="reconciliation_review_completed",
            entity_type="reconciliation_run",
            entity_id=str(latest_run["id"]),
            client_id=application["client_id"],
            application_id=application_id,
            after_data={"reconciliation_review_percent": 100},
        )
    return {"updated_count": len(typed_items), "workflow": workflow}


@router.get("/applications/{application_id}/reconciliation")
async def get_reconciliation(
    application_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    await require_firm_row(store, "applications", application_id, user.firm_id)
    runs = await store.list_rows(
        "reconciliation_runs",
        {"application_id": application_id},
        order="created_at",
        desc=True,
        limit=1,
    )
    if not runs:
        workflow = await get_workflow_progress(store, application_id)
        return {
            "summary": {},
            "items": [],
            "review_progress": workflow["reconciliation"],
        }
    items = await store.list_rows("reconciliation_items", {"reconciliation_run_id": runs[0]["id"]})
    workflow = await get_workflow_progress(store, application_id)
    return {
        **runs[0],
        "items": items,
        "review_progress": workflow["reconciliation"],
    }


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
    if not summary["readiness"]["main_export_enabled"]:
        raise HTTPException(
            status_code=409,
            detail="Complete Validation Review before exporting the GST preparation pack",
        )
    files = {
        "preparatory_report_pdf": (
            "GST_Readiness_Preparatory_Report.pdf",
            generate_readiness_pdf(summary),
            "application/pdf",
        ),
        "document_manifest_csv": (
            "Document_Manifest.csv",
            generate_document_manifest_csv(summary["document_manifest"]),
            "text/csv; charset=utf-8",
        ),
        "normalized_sales_csv": (
            "Normalized_Sales_Data.csv",
            generate_invoice_csv(summary["sales_records"]),
            "text/csv; charset=utf-8",
        ),
        "normalized_purchase_csv": (
            "Normalized_Purchase_Data.csv",
            generate_invoice_csv(summary["purchase_records"]),
            "text/csv; charset=utf-8",
        ),
        "validation_summary_csv": (
            "Validation_Summary.csv",
            generate_validation_csv(summary["validation"]["findings"]),
            "text/csv; charset=utf-8",
        ),
    }
    files["export_pack_zip"] = (
        "OBLIQ_GST_Preparation_Export_Pack.zip",
        generate_export_archive(
            {filename: content for filename, content, _mime_type in files.values()}
        ),
        "application/zip",
    )
    generation_id = uuid4().hex
    output: dict[str, str] = {}
    for key, (filename, content, mime_type) in files.items():
        path = f"{user.firm_id}/{client['id']}/{application_id}/exports/{generation_id}/{filename}"
        await store.upload_file(settings.supabase_exports_bucket, path, content, mime_type)
        output[key] = await store.create_signed_url(settings.supabase_exports_bucket, path, 1800)
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="gst_export_pack_generated",
        entity_type="application",
        entity_id=application_id,
        client_id=client["id"],
        application_id=application_id,
        after_data={"generation_id": generation_id, "files": list(output)},
    )
    return output


@router.post("/applications/{application_id}/reconciliation/export")
async def export_reconciliation(
    application_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    client = await store.get_row("clients", application["client_id"])
    assert client is not None
    summary = await build_readiness_summary(store, application=application, client=client)
    if not summary["workflow"]["reconciliation"]["export_enabled"]:
        raise HTTPException(
            status_code=409,
            detail="Complete Reconciliation Review before exporting the reconciliation working",
        )
    files = {
        "reconciliation_report_pdf": (
            "GSTR2B_Reconciliation_Working_Report.pdf",
            generate_reconciliation_pdf(summary),
            "application/pdf",
        ),
        "reconciliation_details_csv": (
            "GSTR2B_Reconciliation_Details.csv",
            generate_reconciliation_csv(summary["reconciliation_items"]),
            "text/csv; charset=utf-8",
        ),
    }
    files["reconciliation_export_zip"] = (
        "OBLIQ_GSTR2B_Reconciliation_Export.zip",
        generate_export_archive(
            {filename: content for filename, content, _mime_type in files.values()}
        ),
        "application/zip",
    )
    generation_id = uuid4().hex
    output: dict[str, str] = {}
    for key, (filename, content, mime_type) in files.items():
        path = (
            f"{user.firm_id}/{client['id']}/{application_id}/reconciliation/"
            f"exports/{generation_id}/{filename}"
        )
        await store.upload_file(settings.supabase_exports_bucket, path, content, mime_type)
        output[key] = await store.create_signed_url(settings.supabase_exports_bucket, path, 1800)
    latest_run = summary["reconciliation"].get("run") or {}
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="reconciliation_export_generated",
        entity_type="reconciliation_run",
        entity_id=str(latest_run.get("id") or application_id),
        client_id=client["id"],
        application_id=application_id,
        after_data={"generation_id": generation_id, "files": list(output)},
    )
    return output


@router.post("/applications/{application_id}/approve")
async def approve_application(
    application_id: str,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    await require_firm_row(store, "applications", application_id, user.firm_id)
    raise HTTPException(
        status_code=409,
        detail="Available after document processing and review.",
    )


@router.post("/applications/{application_id}/return")
async def return_to_preparer(
    application_id: str,
    payload: ReturnToPreparer,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    updated = await store.update_row(
        "applications",
        application_id,
        {"status": "extraction_review", "final_notes": payload.notes},
    )
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
    safe = "".join(
        char if char.isalnum() or char in ".-_" else "_"
        for char in (file.filename or document_type)
    )
    path = (
        f"{application['firm_id']}/{client['id']}/{application['id']}/filing/{digest[:12]}-{safe}"
    )
    await store.upload_file(
        settings.supabase_documents_bucket,
        path,
        content,
        file.content_type or "application/octet-stream",
    )
    return await store.insert_row(
        "documents",
        {
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
        },
    )


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
        document = await _store_evidence(
            store,
            settings,
            application=application,
            client=client,
            file=filed_return,
            document_type="filed_return",
            user_id=user.user_id,
        )
        update["filed_return_document_id"] = document["id"]
    if payment_challan:
        document = await _store_evidence(
            store,
            settings,
            application=application,
            client=client,
            file=payment_challan,
            document_type="payment_challan",
            user_id=user.user_id,
        )
        update["payment_challan_document_id"] = document["id"]
    updated = await store.update_row("applications", application_id, update)
    assert updated is not None
    return updated
