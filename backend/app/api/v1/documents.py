from __future__ import annotations

import hashlib
import hmac
import mimetypes
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)

from app.config import Settings, get_settings
from app.dependencies import current_user, require_firm_row, require_roles
from app.repositories import DataStore, get_store
from app.schemas.auth import UserContext
from app.schemas.documents import (
    BulkExtractionReview,
    DocumentReclassification,
    ExtractionUpdate,
    ReviewAction,
)
from app.services.audit import record_audit
from app.services.document_processing.ingestion import ArchiveValidationError, read_safe_zip
from app.services.document_processing.pipeline import (
    ingest_document,
    process_ingested_document,
    submit_ingested_documents,
)
from app.services.document_processing.portfolio import build_portfolio
from app.services.document_processing.processor import (
    DocumentProcessor,
    persist_uploaded_document,
)
from app.services.document_processing.taxonomy import BUSINESS_DOCUMENT_TYPES
from app.services.rag.document_indexing import index_document, remove_document_chunks
from app.services.secure_upload import (
    SecureUploadTokenError,
    SecureUploadValidationError,
    create_secure_upload_link,
    resolve_secure_upload_context,
)
from app.services.secure_upload import (
    public_upload_context as build_public_upload_context,
)

router = APIRouter(tags=["documents"])


async def _resolve_public_token(store: DataStore, settings: Settings, raw_token: str):
    try:
        return await resolve_secure_upload_context(store, settings, raw_token)
    except SecureUploadTokenError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/applications/{application_id}/upload-link", status_code=201)
async def create_upload_link(
    application_id: str,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    created = await create_secure_upload_link(
        store,
        settings,
        application=application,
        created_by_user_id=user.user_id,
    )
    return {
        "id": created.id,
        "token": created.raw_token,
        "expires_at": created.expires_at,
        "upload_url": created.upload_url,
    }


@router.get("/public/upload/{token}")
async def public_upload_context(
    token: str,
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    context = await _resolve_public_token(store, settings, token)
    payload = await build_public_upload_context(store, context)
    payload["allowed_extensions"] = sorted(settings.allowed_extensions)
    payload["maximum_size_mb"] = settings.max_upload_mb
    return payload


@router.get("/public/upload/{token}/status")
async def public_upload_status(
    token: str,
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return await public_upload_context(token, store, settings)


@router.post("/public/upload/{token}", status_code=201)
async def public_upload_document(
    token: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    requirement_id: str = Form(...),
    store: DataStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    context = await _resolve_public_token(store, settings, token)
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    try:
        document = await ingest_document(
            store,
            settings,
            context=context,
            explicit_requirement_id=requirement_id,
            filename=file.filename or "upload.bin",
            declared_mime_type=file.content_type or "application/octet-stream",
            content=content,
        )
    except SecureUploadValidationError as exc:
        status_code = 409 if exc.code == "duplicate" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return {
        "id": document["id"],
        "requirement_id": document["requirement_id"],
        "original_name": document["original_name"],
        "upload_status": "uploaded",
        "processing_status": document["processing_status"],
    }


async def _bulk_ingest(
    *,
    store: DataStore,
    settings: Settings,
    context: Any,
    files: list[tuple[str, str, bytes]],
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    for filename, mime_type, content in files:
        document = await ingest_document(
            store,
            settings,
            context=context,
            filename=filename,
            declared_mime_type=mime_type,
            content=content,
        )
        documents.append(document)
    return {"documents": documents, "count": len(documents)}


@router.post("/public/upload/{token}/submit", status_code=202)
async def submit_public_upload_batch(
    token: str,
    background_tasks: BackgroundTasks,
    store: DataStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    context = await _resolve_public_token(store, settings, token)
    try:
        batch, document_ids = await submit_ingested_documents(store, context=context)
    except SecureUploadValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    for document_id in document_ids:
        background_tasks.add_task(process_ingested_document, store, settings, document_id)
    await record_audit(
        store,
        firm_id=context.application["firm_id"],
        user_id=None,
        action="document_batch_submitted",
        entity_type="document_submission_batch",
        entity_id=batch["id"],
        client_id=context.client["id"],
        application_id=context.application["id"],
        demo_session_id=context.application.get("demo_session_id"),
        metadata={"document_count": len(document_ids)},
    )
    return batch


@router.post("/public/upload/{token}/bulk-folder", status_code=201)
async def public_bulk_folder_upload(
    token: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    store: DataStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    if len(files) > settings.bulk_upload_max_files:
        raise HTTPException(status_code=400, detail="Too many files in bulk upload")
    context = await _resolve_public_token(store, settings, token)
    total_limit = settings.bulk_upload_max_total_mb * 1024 * 1024
    payloads: list[tuple[str, str, bytes]] = []
    total = 0
    for file in files:
        content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
        total += len(content)
        if total > total_limit:
            raise HTTPException(status_code=400, detail="Bulk upload is too large")
        payloads.append(
            (
                file.filename or "upload.bin",
                file.content_type or "application/octet-stream",
                content,
            )
        )
    try:
        return await _bulk_ingest(
            store=store,
            settings=settings,
            context=context,
            files=payloads,
            background_tasks=background_tasks,
        )
    except SecureUploadValidationError as exc:
        raise HTTPException(
            status_code=409 if exc.code == "duplicate" else 400,
            detail=str(exc),
        ) from exc


@router.post("/public/upload/{token}/bulk-zip", status_code=201)
async def public_bulk_zip_upload(
    token: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    store: DataStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    context = await _resolve_public_token(store, settings, token)
    compressed = await file.read(settings.bulk_upload_max_total_mb * 1024 * 1024 + 1)
    try:
        entries = read_safe_zip(
            compressed,
            allowed_extensions=settings.allowed_extensions,
            max_files=settings.bulk_upload_max_files,
            max_total_bytes=settings.bulk_upload_max_total_mb * 1024 * 1024,
        )
        portable_mimes = {
            ".csv": "text/csv",
            ".json": "application/json",
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        payloads = [
            (
                entry.name,
                portable_mimes.get(
                    Path(entry.name).suffix.lower(),
                    mimetypes.guess_type(entry.name)[0] or "application/octet-stream",
                ),
                entry.content,
            )
            for entry in entries
        ]
        return await _bulk_ingest(
            store=store,
            settings=settings,
            context=context,
            files=payloads,
            background_tasks=background_tasks,
        )
    except ArchiveValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SecureUploadValidationError as exc:
        raise HTTPException(
            status_code=409 if exc.code == "duplicate" else 400,
            detail=str(exc),
        ) from exc


@router.get("/applications/{application_id}/documents")
async def list_documents(
    application_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> list[dict]:
    await require_firm_row(store, "applications", application_id, user.firm_id)
    return await store.list_rows(
        "documents",
        {"application_id": application_id},
        order="created_at",
        desc=True,
    )


@router.get("/applications/{application_id}/documents/extraction-summary")
async def extraction_summary(
    application_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict[str, Any]:
    await require_firm_row(store, "applications", application_id, user.firm_id)
    documents = await store.list_rows(
        "documents", {"application_id": application_id}, order="created_at", desc=True
    )
    extractions = await store.list_rows("document_extractions")
    by_document = {
        row["document_id"]: row
        for row in extractions
        if row.get("document_id") in {document["id"] for document in documents}
    }
    records = await store.list_rows(
        "invoice_records", {"application_id": application_id}, order="created_at"
    )
    return {
        "documents": [
            {**document, "extraction": by_document.get(document["id"])} for document in documents
        ],
        "records": records,
    }


@router.get("/applications/{application_id}/documents/portfolio")
async def extraction_portfolio(
    application_id: str,
    scope: str = Query(default="combined"),
    user: UserContext = Depends(current_user),
    store: DataStore = Depends(get_store),
) -> dict[str, Any]:
    await require_firm_row(store, "applications", application_id, user.firm_id)
    records = await store.list_rows(
        "invoice_records", {"application_id": application_id}, order="created_at"
    )
    try:
        return build_portfolio(records, scope)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/applications/{application_id}/extractions/bulk-review")
async def bulk_review_extractions(
    application_id: str,
    payload: BulkExtractionReview,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(require_roles("firm_admin", "reviewer")),
    store: DataStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    requested_ids = list(dict.fromkeys(payload.record_ids))
    records = [await store.get_row("invoice_records", record_id) for record_id in requested_ids]
    if any(
        record is None
        or str(record.get("application_id")) != str(application_id)
        or str(record.get("firm_id")) != str(user.firm_id)
        for record in records
    ):
        raise HTTPException(status_code=404, detail="One or more extraction records were not found")

    now = datetime.now(UTC).isoformat()
    review_status = "approved" if payload.action == "approve" else "rejected"
    typed_records = [record for record in records if record is not None]
    for record in typed_records:
        await store.update_row(
            "invoice_records",
            record["id"],
            {
                "review_status": review_status,
                "reviewed_by": user.user_id,
                "reviewed_at": now,
                "review_notes": payload.notes,
            },
        )

    document_ids = {str(record["document_id"]) for record in typed_records}
    for document_id in document_ids:
        document_records = await store.list_rows("invoice_records", {"document_id": document_id})
        extraction_rows = await store.list_rows(
            "document_extractions", {"document_id": document_id}, limit=1
        )
        if payload.action == "approve" and document_records and all(
            row.get("review_status") in {"approved", "edited_and_approved"}
            for row in document_records
        ):
            if extraction_rows:
                await store.update_row(
                    "document_extractions",
                    extraction_rows[0]["id"],
                    {
                        "review_status": "approved",
                        "reviewed_by": user.user_id,
                        "reviewed_at": now,
                        "review_notes": payload.notes,
                    },
                )
            await store.update_row("documents", document_id, {"processing_status": "approved"})
            background_tasks.add_task(index_document, store, settings, document_id)
        elif payload.action == "reject":
            if extraction_rows:
                await store.update_row(
                    "document_extractions",
                    extraction_rows[0]["id"],
                    {
                        "review_status": "rejected",
                        "reviewed_by": user.user_id,
                        "reviewed_at": now,
                        "review_notes": payload.notes,
                    },
                )
            await store.update_row("documents", document_id, {"processing_status": "needs_review"})
            background_tasks.add_task(remove_document_chunks, store, document_id)

    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action=f"extraction.bulk_{payload.action}",
        entity_type="application",
        entity_id=application_id,
        client_id=application["client_id"],
        application_id=application_id,
        metadata={"record_count": len(typed_records), "document_count": len(document_ids)},
    )
    return {
        "action": payload.action,
        "updated_count": len(typed_records),
        "document_count": len(document_ids),
    }


@router.post("/documents/{document_id}/reclassify")
async def reclassify_document(
    document_id: str,
    payload: DocumentReclassification,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict[str, Any]:
    document = await require_firm_row(store, "documents", document_id, user.firm_id)
    if payload.document_type not in BUSINESS_DOCUMENT_TYPES | {"gstr2b"}:
        raise HTTPException(status_code=400, detail="Unsupported document classification")
    requirement_id = None
    if payload.document_type in BUSINESS_DOCUMENT_TYPES:
        requirements = await store.list_rows(
            "document_requirements",
            {
                "application_id": document["application_id"],
                "requirement_type": payload.document_type,
            },
            limit=1,
        )
        if requirements:
            requirement_id = requirements[0]["id"]
            await store.update_row("document_requirements", requirement_id, {"status": "received"})
    updated = await store.update_row(
        "documents",
        document_id,
        {
            "document_type": payload.document_type,
            "classification_source": "ca_review",
            "requirement_id": requirement_id,
            "processing_status": "awaiting_processing",
        },
    )
    assert updated is not None
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="document_reclassified",
        entity_type="document",
        entity_id=document_id,
        client_id=document["client_id"],
        application_id=document["application_id"],
        before_data={"document_type": document.get("document_type")},
        after_data={"document_type": payload.document_type},
    )
    return updated


@router.post("/applications/{application_id}/documents", status_code=201)
async def authenticated_upload(
    application_id: str,
    file: UploadFile = File(...),
    requirement_type: str = Form(...),
    user: UserContext = Depends(require_roles("firm_admin", "gst_preparer", "reviewer")),
    store: DataStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    client = await store.get_row("clients", application["client_id"])
    assert client is not None
    try:
        return await persist_uploaded_document(
            store,
            settings,
            application=application,
            client=client,
            filename=file.filename or "upload.bin",
            mime_type=file.content_type or "application/octet-stream",
            content=await file.read(),
            requirement_type=requirement_type,
            source="dashboard",
            uploaded_by_user_id=user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    document = await require_firm_row(store, "documents", document_id, user.firm_id)
    signed_url = await store.create_signed_url(
        settings.supabase_documents_bucket,
        document["storage_path"],
    )
    return {**document, "signed_url": signed_url}


@router.post("/documents/{document_id}/process")
async def process_document(
    document_id: str,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    await require_firm_row(store, "documents", document_id, user.firm_id)
    await DocumentProcessor(store, settings).process(document_id)
    processed = await store.get_row("documents", document_id)
    if not processed:
        raise HTTPException(status_code=404, detail="Document not found")
    return processed


@router.get("/documents/{document_id}/extraction")
async def get_extraction(
    document_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    await require_firm_row(store, "documents", document_id, user.firm_id)
    rows = await store.list_rows("document_extractions", {"document_id": document_id}, limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail="Extraction not found")
    return rows[0]


@router.patch("/documents/{document_id}/extraction")
async def update_extraction(
    document_id: str,
    payload: ExtractionUpdate,
    background_tasks: BackgroundTasks,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    document = await require_firm_row(store, "documents", document_id, user.firm_id)
    rows = await store.list_rows("document_extractions", {"document_id": document_id}, limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail="Extraction not found")
    try:
        await DocumentProcessor(store, settings).replace_reviewed_records(
            document, payload.structured_data
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Corrected extraction is invalid") from exc
    updated = await store.update_row(
        "document_extractions",
        rows[0]["id"],
        {
            "structured_data": payload.structured_data,
            "review_status": "edited_and_approved",
            "reviewed_by": user.user_id,
            "reviewed_at": datetime.now(UTC).isoformat(),
            "review_notes": payload.review_notes,
        },
    )
    await store.update_row("documents", document_id, {"processing_status": "approved"})
    background_tasks.add_task(index_document, store, settings, document_id)
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="extraction.edited_and_approved",
        entity_type="document_extraction",
        entity_id=rows[0]["id"],
        client_id=document["client_id"],
        application_id=document["application_id"],
        before_data=rows[0]["structured_data"],
        after_data=payload.structured_data,
    )
    assert updated is not None
    return updated


@router.post("/documents/{document_id}/approve")
async def approve_extraction(
    document_id: str,
    payload: ReviewAction,
    background_tasks: BackgroundTasks,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    await require_firm_row(store, "documents", document_id, user.firm_id)
    rows = await store.list_rows("document_extractions", {"document_id": document_id}, limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail="Extraction not found")
    updated = await store.update_row(
        "document_extractions",
        rows[0]["id"],
        {
            "review_status": "approved",
            "reviewed_by": user.user_id,
            "reviewed_at": datetime.now(UTC).isoformat(),
            "review_notes": payload.notes,
        },
    )
    await store.update_row("documents", document_id, {"processing_status": "approved"})
    background_tasks.add_task(index_document, store, settings, document_id)
    assert updated is not None
    return updated


@router.post("/documents/{document_id}/reject")
async def reject_extraction(
    document_id: str,
    payload: ReviewAction,
    background_tasks: BackgroundTasks,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    await require_firm_row(store, "documents", document_id, user.firm_id)
    rows = await store.list_rows("document_extractions", {"document_id": document_id}, limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail="Extraction not found")
    updated = await store.update_row(
        "document_extractions",
        rows[0]["id"],
        {
            "review_status": "rejected",
            "reviewed_by": user.user_id,
            "reviewed_at": datetime.now(UTC).isoformat(),
            "review_notes": payload.notes,
        },
    )
    await store.update_row("documents", document_id, {"processing_status": "rejected"})
    background_tasks.add_task(remove_document_chunks, store, document_id)
    assert updated is not None
    return updated


@router.get("/local-files/{bucket}/{path:path}", include_in_schema=False)
async def local_file(
    bucket: str,
    path: str,
    expires: int = Query(...),
    signature: str = Query(...),
    store: DataStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> Response:
    if store.name != "memory" or expires < int(time.time()):
        raise HTTPException(status_code=404, detail="File not found")
    message = f"{bucket}:{path}:{expires}"
    expected = hmac.new(
        settings.upload_token_pepper.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=403, detail="Invalid file signature")
    content = await store.download_file(bucket, path)
    media_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    return Response(content=content, media_type=media_type)
