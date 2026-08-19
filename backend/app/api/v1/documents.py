from __future__ import annotations

import hashlib
import hmac
import mimetypes
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status

from app.config import Settings, get_settings
from app.dependencies import current_user, require_firm_row, require_roles
from app.repositories import DataStore, get_store
from app.schemas.auth import UserContext
from app.schemas.documents import ExtractionUpdate, ReviewAction
from app.services.audit import record_audit
from app.services.document_processing.processor import DocumentProcessor, persist_uploaded_document
from app.services.upload_tokens import UploadTokenRecord, hash_upload_token, issue_upload_token, verify_upload_token

router = APIRouter(tags=["documents"])


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


async def _resolve_public_token(store: DataStore, settings: Settings, raw_token: str) -> tuple[dict, dict, dict, list[dict]]:
    token_hash = hash_upload_token(raw_token, settings.upload_token_pepper)
    rows = await store.list_rows("upload_links", {"token_hash": token_hash}, limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail="Upload link not found")
    row = rows[0]
    record = UploadTokenRecord(
        application_id=row["application_id"],
        client_id=row["client_id"],
        token_hash=row["token_hash"],
        expires_at=_parse_datetime(row["expires_at"]),
        revoked_at=_parse_datetime(row["revoked_at"]) if row.get("revoked_at") else None,
    )
    if not verify_upload_token(raw_token, record, pepper=settings.upload_token_pepper):
        raise HTTPException(status_code=410, detail="Upload link has expired or was revoked")
    application = await store.get_row("applications", record.application_id)
    client = await store.get_row("clients", record.client_id)
    if not application or not client:
        raise HTTPException(status_code=404, detail="Upload application not found")
    checklist = await store.list_rows("document_requirements", {"application_id": application["id"]}, order="label")
    return row, application, client, checklist


@router.post("/applications/{application_id}/upload-link", status_code=201)
async def create_upload_link(
    application_id: str,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    raw_token, record = issue_upload_token(
        application_id=application_id,
        client_id=application["client_id"],
        pepper=settings.upload_token_pepper,
        ttl=timedelta(hours=settings.upload_link_ttl_hours),
    )
    row = await store.insert_row("upload_links", {
        "application_id": record.application_id,
        "client_id": record.client_id,
        "token_hash": record.token_hash,
        "expires_at": record.expires_at.isoformat(),
        "revoked_at": None,
    })
    return {
        "id": row["id"],
        "token": raw_token,
        "expires_at": record.expires_at,
        "upload_url": f"{settings.frontend_url}/upload/{raw_token}",
    }


@router.get("/public/upload/{token}")
async def public_upload_context(
    token: str,
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _, application, client, checklist = await _resolve_public_token(store, settings, token)
    firm = await store.get_row("firms", application["firm_id"])
    return {"firm": firm, "client": client, "application": application, "checklist": checklist}


@router.post("/public/upload/{token}", status_code=201)
async def public_upload_document(
    token: str,
    file: UploadFile = File(...),
    requirement_type: str = Form(...),
    store: DataStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    _, application, client, _ = await _resolve_public_token(store, settings, token)
    content = await file.read()
    try:
        document = await persist_uploaded_document(
            store,
            settings,
            application=application,
            client=client,
            filename=file.filename or "upload.bin",
            mime_type=file.content_type or "application/octet-stream",
            content=content,
            requirement_type=requirement_type,
            source="secure_link",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await record_audit(
        store,
        firm_id=application["firm_id"],
        user_id=None,
        action="document.public_uploaded",
        entity_type="document",
        entity_id=document["id"],
        client_id=client["id"],
        application_id=application["id"],
        after_data={"filename": document["original_name"], "source": "secure_link"},
    )
    return document


@router.get("/applications/{application_id}/documents")
async def list_documents(
    application_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> list[dict]:
    await require_firm_row(store, "applications", application_id, user.firm_id)
    return await store.list_rows("documents", {"application_id": application_id}, order="created_at", desc=True)


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
    signed_url = await store.create_signed_url(settings.supabase_documents_bucket, document["storage_path"])
    return {**document, "signed_url": signed_url}


@router.post("/documents/{document_id}/process")
async def process_document(
    document_id: str,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    await require_firm_row(store, "documents", document_id, user.firm_id)
    return await DocumentProcessor(store, settings).process(document_id)


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
    document = await require_firm_row(store, "documents", document_id, user.firm_id)
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
    expected = hmac.new(settings.upload_token_pepper.encode(), message.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=403, detail="Invalid file signature")
    content = await store.download_file(bucket, path)
    media_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    return Response(content=content, media_type=media_type)
