from __future__ import annotations

import hashlib
import hmac
import mimetypes
import time
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import (
    APIRouter,
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
from app.schemas.documents import ExtractionUpdate, ReviewAction
from app.services.audit import record_audit
from app.services.document_processing.processor import (
    DocumentProcessor,
    persist_uploaded_document,
)
from app.services.secure_upload import (
    SecureUploadTokenError,
    SecureUploadValidationError,
    create_secure_upload_link,
    resolve_secure_upload_context,
    store_secure_document,
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
    file: UploadFile = File(...),
    requirement_id: str = Form(...),
    store: DataStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    context = await _resolve_public_token(store, settings, token)
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    try:
        document = await store_secure_document(
            store,
            settings,
            context=context,
            requirement_id=requirement_id,
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
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    document = await require_firm_row(store, "documents", document_id, user.firm_id)
    rows = await store.list_rows("document_extractions", {"document_id": document_id}, limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail="Extraction not found")
    updated = await store.update_row("document_extractions", rows[0]["id"], {
        "structured_data": payload.structured_data,
        "review_status": "edited_and_approved",
        "reviewed_by": user.user_id,
        "reviewed_at": datetime.now(UTC).isoformat(),
        "review_notes": payload.review_notes,
    })
    await store.update_row("documents", document_id, {"processing_status": "approved"})
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
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    await require_firm_row(store, "documents", document_id, user.firm_id)
    rows = await store.list_rows("document_extractions", {"document_id": document_id}, limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail="Extraction not found")
    updated = await store.update_row("document_extractions", rows[0]["id"], {
        "review_status": "approved",
        "reviewed_by": user.user_id,
        "reviewed_at": datetime.now(UTC).isoformat(),
        "review_notes": payload.notes,
    })
    await store.update_row("documents", document_id, {"processing_status": "approved"})
    assert updated is not None
    return updated


@router.post("/documents/{document_id}/reject")
async def reject_extraction(
    document_id: str,
    payload: ReviewAction,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    await require_firm_row(store, "documents", document_id, user.firm_id)
    rows = await store.list_rows("document_extractions", {"document_id": document_id}, limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail="Extraction not found")
    updated = await store.update_row("document_extractions", rows[0]["id"], {
        "review_status": "rejected",
        "reviewed_by": user.user_id,
        "reviewed_at": datetime.now(UTC).isoformat(),
        "review_notes": payload.notes,
    })
    await store.update_row("documents", document_id, {"processing_status": "rejected"})
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
