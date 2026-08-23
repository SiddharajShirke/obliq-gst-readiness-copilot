"""CA-controlled assistant mutations with preview, confirmation, and audit."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import Settings
from app.repositories.base import DataStore
from app.services.alert_explanations import build_alert_evidence
from app.services.audit import record_audit
from app.services.document_collection import get_document_collection_status
from app.services.document_processing.processor import DocumentProcessor
from app.services.rag.application_context import draft_missing_document_reminder
from app.services.validation_corrections import apply_correction_proposal


class ActionConflict(ValueError):
    """The proposal is no longer safe to execute."""


_REVIEW_ROLES = frozenset({"firm_admin", "reviewer"})
_ALLOWED_ACTIONS = frozenset(
    {
        "approve_extraction",
        "reject_extraction",
        "edit_and_approve_extraction",
        "apply_validation_correction",
        "mark_validation_reviewed",
        "mark_reconciliation_reviewed",
        "raise_reconciliation_alert",
        "draft_reminder",
    }
)


def _now() -> datetime:
    return datetime.now(UTC)


def _fingerprint(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _ensure_role(role: str, action_type: str) -> None:
    if action_type == "draft_reminder":
        if role not in {*_REVIEW_ROLES, "gst_preparer"}:
            raise PermissionError("This role cannot draft reminders")
        return
    if role not in _REVIEW_ROLES:
        raise PermissionError("This action requires a firm administrator or reviewer")


async def _application(
    store: DataStore, application_id: str, firm_id: str
) -> dict[str, Any]:
    application = await store.get_row("applications", application_id)
    if not application or str(application.get("firm_id")) != str(firm_id):
        raise LookupError("Application not found")
    return application


async def _target_snapshot(
    store: DataStore,
    *,
    application: dict[str, Any],
    action_type: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    application_id = str(application["id"])
    if action_type in {
        "approve_extraction",
        "reject_extraction",
        "edit_and_approve_extraction",
    }:
        document = await store.get_row("documents", str(payload.get("document_id") or ""))
        if not document or str(document.get("application_id")) != application_id:
            raise LookupError("Document not found in this application")
        rows = await store.list_rows(
            "document_extractions", {"document_id": document["id"]}, limit=1
        )
        if not rows:
            raise LookupError("Document extraction not found")
        extraction = rows[0]
        snapshot = {
            "document_id": document["id"],
            "document_status": document.get("processing_status"),
            "extraction_id": extraction["id"],
            "review_status": extraction.get("review_status"),
            "structured_data": extraction.get("structured_data"),
        }
        preview = {
            "title": action_type.replace("_", " ").title(),
            "target": document.get("original_name") or document["id"],
            "before": {"review_status": extraction.get("review_status")},
            "after": {
                "review_status": (
                    "rejected" if action_type == "reject_extraction" else "approved"
                )
            },
            "affected_count": 1,
        }
        return snapshot, preview

    if action_type == "mark_validation_reviewed":
        finding = await store.get_row(
            "validation_findings", str(payload.get("finding_id") or "")
        )
        if not finding or str(finding.get("application_id")) != application_id:
            raise LookupError("Validation finding not found in this application")
        return (
            {"id": finding["id"], "status": finding.get("status")},
            {
                "title": "Mark validation finding reviewed",
                "target": finding.get("message") or finding["id"],
                "before": {"status": finding.get("status")},
                "after": {"status": "accepted"},
                "affected_count": 1,
            },
        )

    if action_type in {"mark_reconciliation_reviewed", "raise_reconciliation_alert"}:
        item = await store.get_row(
            "reconciliation_items", str(payload.get("item_id") or "")
        )
        run = (
            await store.get_row("reconciliation_runs", item["reconciliation_run_id"])
            if item
            else None
        )
        if not item or not run or str(run.get("application_id")) != application_id:
            raise LookupError("Reconciliation item not found in this application")
        existing_alerts = await store.list_rows(
            "alerts", {"reconciliation_item_id": item["id"]}, limit=1
        )
        snapshot = {
            "id": item["id"],
            "review_status": item.get("review_status"),
            "match_status": item.get("match_status"),
            "evidence": item.get("evidence") or {},
            "existing_alert_id": existing_alerts[0]["id"] if existing_alerts else None,
        }
        preview = {
            "title": action_type.replace("_", " ").title(),
            "target": item["id"],
            "before": {
                "review_status": item.get("review_status"),
                "alert_exists": bool(existing_alerts),
            },
            "after": {
                "review_status": (
                    "reviewed"
                    if action_type == "mark_reconciliation_reviewed"
                    else item.get("review_status")
                ),
                "alert_exists": action_type == "raise_reconciliation_alert",
            },
            "affected_count": 1,
        }
        return snapshot, preview

    if action_type == "apply_validation_correction":
        correction = await store.get_row(
            "validation_correction_proposals",
            str(payload.get("correction_proposal_id") or ""),
        )
        if not correction or str(correction.get("application_id")) != application_id:
            raise LookupError("Validation correction proposal not found")
        return (
            {
                "id": correction["id"],
                "status": correction.get("status"),
                "changes": correction.get("changes") or [],
            },
            {
                "title": "Apply validation correction",
                "target": correction["id"],
                "before": {"status": correction.get("status")},
                "after": {"status": "applied"},
                "changes": correction.get("changes") or [],
                "affected_count": len(correction.get("record_ids") or []),
            },
        )

    if action_type == "draft_reminder":
        collection = await get_document_collection_status(store, application_id)
        missing = [
            {"id": row["id"], "label": row["label"], "status": row["status"]}
            for row in collection.get("requirements", [])
            if row.get("status") != "received"
        ]
        return (
            {"requirements": missing},
            {
                "title": "Draft missing-document reminder",
                "target": application.get("period_label") or application_id,
                "missing_documents": [row["label"] for row in missing],
                "affected_count": len(missing),
            },
        )
    raise ValueError("Unsupported assistant action")


async def create_action_proposal(
    store: DataStore,
    *,
    firm_id: str,
    user_id: str,
    role: str,
    application_id: str,
    conversation_id: str,
    action_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if action_type not in _ALLOWED_ACTIONS:
        raise ValueError("Unsupported assistant action")
    _ensure_role(role, action_type)
    application = await _application(store, application_id, firm_id)
    snapshot, preview = await _target_snapshot(
        store,
        application=application,
        action_type=action_type,
        payload=payload,
    )
    now = _now()
    proposal = await store.insert_row(
        "assistant_action_proposals",
        {
            "firm_id": firm_id,
            "user_id": user_id,
            "application_id": application_id,
            "demo_session_id": application.get("demo_session_id"),
            "conversation_id": conversation_id,
            "action_type": action_type,
            "payload": payload,
            "preview": preview,
            "evidence_fingerprint": _fingerprint(snapshot),
            "status": "pending_confirmation",
            "expires_at": (now + timedelta(minutes=15)).isoformat(),
        },
    )
    await record_audit(
        store,
        firm_id=firm_id,
        user_id=user_id,
        action="assistant_action_proposed",
        entity_type="assistant_action_proposal",
        entity_id=proposal["id"],
        client_id=application.get("client_id"),
        application_id=application_id,
        demo_session_id=application.get("demo_session_id"),
        metadata={"action_type": action_type, "conversation_id": conversation_id},
    )
    return proposal


def _reconciliation_alert_type(item: dict[str, Any]) -> str:
    status = str(item.get("match_status") or "")
    flags = {str(value).lower() for value in item.get("special_flags") or []}
    if "itc_not_available" in flags:
        return "ITC_NOT_AVAILABLE"
    if "rcm" in flags:
        return "RCM"
    mapping = {
        "invoice_number_mismatch": "INVOICE_NUMBER_MISMATCH",
        "books_only": "BOOKS_ONLY",
        "gstr2b_only": "GSTR2B_ONLY",
        "ambiguous_match": "AMBIGUOUS_MATCH",
        "duplicate": "DUPLICATE",
    }
    if status in mapping:
        return mapping[status]
    fields = set((item.get("evidence") or {}).get("difference_fields") or [])
    if fields == {"taxable_value"}:
        return "TAXABLE_VALUE_MISMATCH"
    if fields & {"igst", "cgst", "sgst", "cess", "total_tax"}:
        return "TAX_MISMATCH"
    return "VALUE_MISMATCH" if status == "value_mismatch" else "OTHER_RECONCILIATION_REVIEW"


async def _execute(
    store: DataStore,
    settings: Settings,
    *,
    proposal: dict[str, Any],
    application: dict[str, Any],
    user_id: str,
) -> dict[str, Any]:
    action_type = str(proposal["action_type"])
    payload = proposal.get("payload") or {}
    now = _now().isoformat()
    if action_type in {
        "approve_extraction",
        "reject_extraction",
        "edit_and_approve_extraction",
    }:
        document_id = str(payload["document_id"])
        rows = await store.list_rows(
            "document_extractions", {"document_id": document_id}, limit=1
        )
        extraction = rows[0]
        review_status = "rejected" if action_type == "reject_extraction" else "approved"
        if action_type == "edit_and_approve_extraction":
            document = await store.get_row("documents", document_id)
            assert document is not None
            await DocumentProcessor(store, settings).replace_reviewed_records(
                document, payload.get("structured_data") or {}
            )
        update = {
            "review_status": review_status,
            "reviewed_by": user_id,
            "reviewed_at": now,
            "review_notes": payload.get("notes"),
        }
        if action_type == "edit_and_approve_extraction":
            update["structured_data"] = payload.get("structured_data") or {}
            update["review_status"] = "edited_and_approved"
        result = await store.update_row("document_extractions", extraction["id"], update)
        await store.update_row(
            "documents",
            document_id,
            {"processing_status": "rejected" if review_status == "rejected" else "approved"},
        )
        return {"entity_type": "document_extraction", "entity": result}

    if action_type == "mark_validation_reviewed":
        result = await store.update_row(
            "validation_findings",
            str(payload["finding_id"]),
            {"status": "accepted", "resolved_by": user_id, "resolved_at": now},
        )
        return {"entity_type": "validation_finding", "entity": result}

    if action_type == "mark_reconciliation_reviewed":
        result = await store.update_row(
            "reconciliation_items",
            str(payload["item_id"]),
            {"review_status": "reviewed", "reviewed_by": user_id, "reviewed_at": now},
        )
        return {"entity_type": "reconciliation_item", "entity": result}

    if action_type == "apply_validation_correction":
        correction = await store.get_row(
            "validation_correction_proposals", str(payload["correction_proposal_id"])
        )
        assert correction is not None
        result = await apply_correction_proposal(store, correction, user_id=user_id)
        return {"entity_type": "validation_correction_proposal", "entity": result}

    if action_type == "raise_reconciliation_alert":
        item = await store.get_row("reconciliation_items", str(payload["item_id"]))
        assert item is not None
        existing = await store.list_rows(
            "alerts", {"reconciliation_item_id": item["id"]}, limit=1
        )
        if existing:
            return {"entity_type": "alert", "entity": existing[0], "already_existed": True}
        client = await store.get_row("clients", application["client_id"])
        alert_type = _reconciliation_alert_type(item)
        evidence = build_alert_evidence(
            alert_type=alert_type,
            client_name=(client or {}).get("business_name") or "Client",
            tax_period=application.get("period_label") or "GST period",
            reconciliation_evidence=item.get("evidence") or {},
        )
        books = (item.get("evidence") or {}).get("books") or {}
        gstr2b = (item.get("evidence") or {}).get("gstr2b") or {}
        identity = books.get("invoice_number") or gstr2b.get("invoice_number") or "GST record"
        alert = await store.insert_row(
            "alerts",
            {
                "firm_id": application["firm_id"],
                "application_id": application["id"],
                "client_id": application["client_id"],
                "reconciliation_item_id": item["id"],
                "alert_type": alert_type,
                "title": alert_type.replace("_", " ").title(),
                "message": f"{identity} requires CA review.",
                "severity": "medium",
                "status": "open",
                "evidence": evidence,
                "ai_explanation": None,
                "ai_explanation_status": "pending",
            },
        )
        return {"entity_type": "alert", "entity": alert}

    if action_type == "draft_reminder":
        collection = await get_document_collection_status(store, str(application["id"]))
        client = await store.get_row("clients", application["client_id"])
        message = draft_missing_document_reminder(
            collection,
            str((client or {}).get("business_name") or "Client"),
            str(application.get("period_label") or "the GST period"),
        )
        reminder = await store.insert_row(
            "reminders",
            {
                "firm_id": application["firm_id"],
                "application_id": application["id"],
                "base_application_id": application.get("base_application_id")
                or application["id"],
                "client_id": application["client_id"],
                "demo_session_id": application.get("demo_session_id"),
                "reminder_type": "missing_document_reminder",
                "draft_message": message,
                "status": "awaiting_approval",
                "provider": None,
            },
        )
        return {"entity_type": "reminder", "entity": reminder}
    raise ValueError("Unsupported assistant action")


async def _owned_proposal(
    store: DataStore,
    *,
    proposal_id: str,
    firm_id: str,
    user_id: str,
    conversation_id: str,
) -> dict[str, Any]:
    proposal = await store.get_row("assistant_action_proposals", proposal_id)
    if (
        not proposal
        or str(proposal.get("firm_id")) != str(firm_id)
        or str(proposal.get("user_id")) != str(user_id)
        or str(proposal.get("conversation_id")) != str(conversation_id)
    ):
        raise LookupError("Assistant action proposal not found")
    return proposal


async def confirm_action_proposal(
    store: DataStore,
    settings: Settings,
    *,
    proposal_id: str,
    firm_id: str,
    user_id: str,
    role: str,
    conversation_id: str,
) -> dict[str, Any]:
    proposal = await _owned_proposal(
        store,
        proposal_id=proposal_id,
        firm_id=firm_id,
        user_id=user_id,
        conversation_id=conversation_id,
    )
    _ensure_role(role, str(proposal["action_type"]))
    if proposal.get("status") != "pending_confirmation":
        raise ActionConflict("Assistant action proposal has already been decided")
    expires_at = datetime.fromisoformat(str(proposal["expires_at"]).replace("Z", "+00:00"))
    if expires_at <= _now():
        await store.update_row("assistant_action_proposals", proposal_id, {"status": "expired"})
        raise ActionConflict("Assistant action proposal has expired")
    application = await _application(store, str(proposal["application_id"]), firm_id)
    snapshot, _ = await _target_snapshot(
        store,
        application=application,
        action_type=str(proposal["action_type"]),
        payload=proposal.get("payload") or {},
    )
    if _fingerprint(snapshot) != proposal.get("evidence_fingerprint"):
        raise ActionConflict("Application data changed; create a fresh proposal")
    now = _now().isoformat()
    await store.update_row(
        "assistant_action_proposals",
        proposal_id,
        {"status": "confirmed", "confirmed_at": now},
    )
    try:
        result = await _execute(
            store,
            settings,
            proposal=proposal,
            application=application,
            user_id=user_id,
        )
    except Exception as exc:
        await store.update_row(
            "assistant_action_proposals",
            proposal_id,
            {"status": "failed", "error_message": type(exc).__name__},
        )
        raise
    executed = await store.update_row(
        "assistant_action_proposals",
        proposal_id,
        {"status": "executed", "executed_at": _now().isoformat(), "result": result},
    )
    assert executed is not None
    await record_audit(
        store,
        firm_id=firm_id,
        user_id=user_id,
        action="assistant_action_executed",
        entity_type="assistant_action_proposal",
        entity_id=proposal_id,
        client_id=application.get("client_id"),
        application_id=application["id"],
        demo_session_id=application.get("demo_session_id"),
        metadata={"action_type": proposal["action_type"], "conversation_id": conversation_id},
    )
    return executed


async def cancel_action_proposal(
    store: DataStore,
    *,
    proposal_id: str,
    firm_id: str,
    user_id: str,
    conversation_id: str,
) -> dict[str, Any]:
    proposal = await _owned_proposal(
        store,
        proposal_id=proposal_id,
        firm_id=firm_id,
        user_id=user_id,
        conversation_id=conversation_id,
    )
    if proposal.get("status") != "pending_confirmation":
        raise ActionConflict("Assistant action proposal has already been decided")
    updated = await store.update_row(
        "assistant_action_proposals",
        proposal_id,
        {"status": "cancelled"},
    )
    assert updated is not None
    return updated
