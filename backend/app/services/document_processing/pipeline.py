"""One scoped intake pipeline shared by individual, folder, and ZIP uploads."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.repositories.base import DataStore
from app.services.audit import record_audit
from app.services.document_processing.ingestion import classify_for_ingestion
from app.services.document_processing.processor import DocumentProcessor
from app.services.document_processing.taxonomy import CLIENT_REQUIREMENTS
from app.services.secure_upload import (
    ResolvedUploadContext,
    SecureUploadValidationError,
    build_storage_path,
    store_secure_document,
    validate_secure_upload,
)


async def ingest_document(
    store: DataStore,
    settings: Settings,
    *,
    context: ResolvedUploadContext,
    filename: str,
    declared_mime_type: str,
    content: bytes,
    explicit_requirement_id: str | None = None,
) -> dict[str, Any]:
    upload_link_id = context.link.get("id")
    requirement = next(
        (row for row in context.checklist if str(row["id"]) == str(explicit_requirement_id)),
        None,
    )
    explicit_category = requirement.get("requirement_type") if requirement else None
    classification = classify_for_ingestion(
        filename=filename,
        mime_type=declared_mime_type,
        content=content,
        explicit_category=explicit_category,
    )
    if explicit_requirement_id and not requirement:
        await record_audit(
            store,
            firm_id=context.application["firm_id"],
            user_id=None,
            action="upload_failed",
            entity_type="upload_link",
            entity_id=context.link.get("id"),
            client_id=context.client["id"],
            application_id=context.application["id"],
            demo_session_id=context.application.get("demo_session_id"),
            metadata={"reason": "requirement_mismatch"},
        )
        raise SecureUploadValidationError(
            "requirement_mismatch", "The selected checklist category is not available"
        )
    if not requirement and classification.document_type in CLIENT_REQUIREMENTS:
        requirement = next(
            (
                row
                for row in context.checklist
                if row.get("requirement_type") == classification.document_type
            ),
            None,
        )
    if requirement:
        document = await store_secure_document(
            store,
            settings,
            context=context,
            requirement_id=str(requirement["id"]),
            filename=filename,
            declared_mime_type=declared_mime_type,
            content=content,
        )
        status = "awaiting_submission" if upload_link_id else "awaiting_processing"
        updated = await store.update_row(
            "documents",
            document["id"],
            {
                "document_type": classification.document_type,
                "classification_source": classification.source,
                "processing_status": status,
                "upload_link_id": upload_link_id,
                "submission_batch_id": None,
                "submitted_at": None,
            },
        )
        return updated or {**document, "document_type": classification.document_type}

    validated = validate_secure_upload(
        settings,
        filename=filename,
        declared_mime_type=declared_mime_type,
        content=content,
    )
    duplicates = await store.list_rows(
        "documents",
        {"application_id": context.application["id"], "sha256": validated.sha256},
    )
    if any(row.get("processing_status") != "upload_failed" for row in duplicates):
        raise SecureUploadValidationError("duplicate", "This file was already uploaded")
    document_id = str(uuid.uuid4())
    storage_path = build_storage_path(
        firm_id=context.application["firm_id"],
        client_id=context.client["id"],
        application_id=context.application["id"],
        demo_session_id=context.application.get("demo_session_id"),
        document_id=document_id,
        safe_name=validated.safe_name,
    )
    await store.upload_file(
        settings.supabase_documents_bucket,
        storage_path,
        content,
        validated.mime_type,
    )
    now = datetime.now(UTC).isoformat()
    processing_status = {
        "developer_ground_truth": "excluded_reference",
        "unknown": "needs_assignment",
    }.get(
        classification.document_type,
        "awaiting_submission" if upload_link_id else "awaiting_processing",
    )
    document = await store.insert_row(
        "documents",
        {
            "id": document_id,
            "firm_id": context.application["firm_id"],
            "client_id": context.client["id"],
            "application_id": context.application["id"],
            "demo_session_id": context.application.get("demo_session_id"),
            "requirement_id": None,
            "source": "secure_link",
            "original_name": validated.original_name,
            "safe_name": validated.safe_name,
            "mime_type": validated.mime_type,
            "storage_bucket": settings.supabase_documents_bucket,
            "storage_path": storage_path,
            "file_size": validated.file_size,
            "sha256": validated.sha256,
            "document_type": classification.document_type,
            "classification_source": classification.source,
            "processing_status": processing_status,
            "upload_link_id": upload_link_id,
            "submission_batch_id": None,
            "submitted_at": None,
            "uploaded_by_user_id": None,
            "uploaded_from_phone": None,
            "upload_completed_at": now,
        },
    )
    await record_audit(
        store,
        firm_id=context.application["firm_id"],
        user_id=None,
        action=(
            "developer_ground_truth_excluded"
            if classification.document_type == "developer_ground_truth"
            else "upload_completed"
        ),
        entity_type="document",
        entity_id=document_id,
        client_id=context.client["id"],
        application_id=context.application["id"],
        demo_session_id=context.application.get("demo_session_id"),
        after_data={
            "document_type": classification.document_type,
            "processing_status": processing_status,
        },
    )
    return document


async def process_ingested_document(store: DataStore, settings: Settings, document_id: str) -> None:
    document = await store.get_row("documents", document_id)
    if not document or document.get("processing_status") in {
        "excluded_reference",
        "needs_assignment",
    }:
        return
    try:
        await DocumentProcessor(store, settings).process(document_id)
    except Exception as exc:
        await store.update_row(
            "documents",
            document_id,
            {
                "processing_status": "processing_failed",
                "processing_error": type(exc).__name__,
            },
        )
    finally:
        document = await store.get_row("documents", document_id)
        batch_id = document.get("submission_batch_id") if document else None
        if batch_id:
            await refresh_submission_batch(store, str(batch_id))


async def submit_ingested_documents(
    store: DataStore,
    *,
    context: ResolvedUploadContext,
) -> tuple[dict[str, Any], list[str]]:
    """Atomically bind the current unsubmitted token-scoped documents to one batch."""
    batch_id = str(uuid.uuid4())
    submitted_at = datetime.now(UTC).isoformat()
    rows = await store.rpc(
        "submit_document_batch",
        {
            "p_upload_link_id": context.link["id"],
            "p_batch_id": batch_id,
            "p_now": submitted_at,
        },
    )
    if not rows:
        raise SecureUploadValidationError(
            "nothing_to_submit", "There are no newly uploaded documents to submit"
        )
    documents = await store.list_rows("documents", {"submission_batch_id": batch_id})
    return rows[0], [str(document["id"]) for document in documents]


async def refresh_submission_batch(store: DataStore, batch_id: str) -> None:
    batch = await store.get_row("document_submission_batches", batch_id)
    if not batch:
        return
    documents = await store.list_rows("documents", {"submission_batch_id": batch_id})
    completed_states = {"ready_for_review", "needs_review", "approved", "rejected", "processed"}
    failed_states = {"processing_failed", "failed"}
    completed = sum(document.get("processing_status") in completed_states for document in documents)
    failed = sum(document.get("processing_status") in failed_states for document in documents)
    active = any(
        document.get("processing_status") in {"awaiting_processing", "processing", "queued"}
        for document in documents
    )
    if active:
        status = "processing"
        completed_at = None
    elif failed and completed:
        status = "partially_completed"
        completed_at = datetime.now(UTC).isoformat()
    elif failed:
        status = "failed"
        completed_at = datetime.now(UTC).isoformat()
    else:
        status = "completed"
        completed_at = datetime.now(UTC).isoformat()
    await store.update_row(
        "document_submission_batches",
        batch_id,
        {
            "status": status,
            "completed_count": completed,
            "failed_count": failed,
            "completed_at": completed_at,
        },
    )
