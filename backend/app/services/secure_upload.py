"""Secure upload-link creation shared by dashboard and Vonage workflows."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from app.config import Settings
from app.repositories.base import DataStore
from app.services.audit import record_audit
from app.services.upload_tokens import (
    UploadTokenRecord,
    hash_upload_token,
    issue_upload_token,
    verify_upload_token,
)


class SecureUploadValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    original_name: str
    safe_name: str
    mime_type: str
    file_size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ResolvedUploadContext:
    link: dict[str, Any]
    firm: dict[str, Any]
    client: dict[str, Any]
    application: dict[str, Any]
    demo_session: dict[str, Any] | None
    checklist: list[dict[str, Any]]


class SecureUploadTokenError(ValueError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def validate_secure_upload(
    settings: Settings,
    *,
    filename: str,
    declared_mime_type: str,
    content: bytes,
) -> ValidatedUpload:
    if not content:
        raise SecureUploadValidationError("empty", "The uploaded file is empty")
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise SecureUploadValidationError(
            "oversized", f"File exceeds {settings.max_upload_mb} MB limit"
        )

    original_name = Path(filename.replace("\\", "/")).name
    extension = Path(original_name).suffix.lower().lstrip(".")
    if extension not in settings.allowed_extensions:
        raise SecureUploadValidationError(
            "unsupported", f"Unsupported file extension: {extension or 'none'}"
        )

    mime_type = (declared_mime_type or "application/octet-stream").split(";", 1)[0].lower()
    allowed_mimes = {
        "pdf": {"application/pdf"},
        "jpg": {"image/jpeg"},
        "jpeg": {"image/jpeg"},
        "png": {"image/png"},
        "csv": {"text/csv", "application/csv", "text/plain"},
        "json": {"application/json", "text/json"},
        "xlsx": {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        },
        "docx": {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        },
    }
    if mime_type not in allowed_mimes.get(extension, set()):
        raise SecureUploadValidationError(
            "mime_mismatch",
            "The declared file type does not match the filename extension",
        )

    valid_signature = False
    if extension == "pdf":
        valid_signature = content.startswith(b"%PDF")
    elif extension in {"jpg", "jpeg"}:
        valid_signature = content.startswith(b"\xff\xd8\xff")
    elif extension == "png":
        valid_signature = content.startswith(b"\x89PNG\r\n\x1a\n")
    elif extension in {"xlsx", "docx"}:
        expected_prefix = "xl/" if extension == "xlsx" else "word/"
        try:
            with ZipFile(BytesIO(content)) as archive:
                names = archive.namelist()
                valid_signature = any(name.startswith(expected_prefix) for name in names)
        except (BadZipFile, OSError):
            valid_signature = False
    elif extension == "csv":
        try:
            decoded = content.decode("utf-8-sig")
            if "\x00" in decoded:
                raise csv.Error("NUL byte in text upload")
            dialect = csv.Sniffer().sniff(decoded[:8192], delimiters=",;\t")
            first_row = next(csv.reader(StringIO(decoded), dialect), None)
            valid_signature = bool(first_row and len(first_row) > 1)
        except (UnicodeDecodeError, csv.Error):
            valid_signature = False
    elif extension == "json":
        try:
            json.loads(content.decode("utf-8-sig"))
            valid_signature = True
        except (UnicodeDecodeError, json.JSONDecodeError):
            valid_signature = False
    if not valid_signature:
        raise SecureUploadValidationError(
            "signature_mismatch",
            "The file content does not match its declared format",
        )

    safe_name = "".join(
        character if character.isalnum() or character in ".-_" else "_"
        for character in original_name
    ).lstrip(".")
    if not safe_name:
        safe_name = f"upload.{extension}"
    return ValidatedUpload(
        original_name=original_name,
        safe_name=safe_name[:180],
        mime_type=mime_type,
        file_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )


def build_storage_path(
    *,
    firm_id: str,
    client_id: str,
    application_id: str,
    demo_session_id: str | None,
    document_id: str,
    safe_name: str,
) -> str:
    parts = [firm_id, client_id]
    if demo_session_id:
        parts.append(demo_session_id)
    parts.extend([application_id, document_id, safe_name])
    return "/".join(parts)


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


async def resolve_secure_upload_context(
    store: DataStore,
    settings: Settings,
    raw_token: str,
) -> ResolvedUploadContext:
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", raw_token):
        raise SecureUploadTokenError(404, "Upload link not found")
    token_hash = hash_upload_token(raw_token, settings.upload_token_pepper)
    rows = await store.list_rows("upload_links", {"token_hash": token_hash}, limit=1)
    if not rows:
        raise SecureUploadTokenError(404, "Upload link not found")
    link = rows[0]
    record = UploadTokenRecord(
        firm_id=str(link.get("firm_id") or ""),
        application_id=str(link["application_id"]),
        client_id=str(link["client_id"]),
        demo_session_id=(str(link["demo_session_id"]) if link.get("demo_session_id") else None),
        requirement_id=(str(link["requirement_id"]) if link.get("requirement_id") else None),
        token_hash=str(link["token_hash"]),
        expires_at=_parse_datetime(link["expires_at"]),
        revoked_at=_parse_datetime(link["revoked_at"]) if link.get("revoked_at") else None,
    )
    if not verify_upload_token(raw_token, record, pepper=settings.upload_token_pepper):
        await record_audit(
            store,
            firm_id=record.firm_id,
            user_id=None,
            action=(
                "upload_token_revoked"
                if record.revoked_at is not None
                else "upload_token_expired"
            ),
            entity_type="upload_link",
            entity_id=link.get("id"),
            client_id=record.client_id,
            application_id=record.application_id,
            demo_session_id=record.demo_session_id,
        )
        raise SecureUploadTokenError(410, "Upload link has expired or was revoked")

    application = await store.get_row("applications", record.application_id)
    client = await store.get_row("clients", record.client_id)
    if (
        not application
        or not client
        or str(application.get("firm_id")) != record.firm_id
        or str(application.get("client_id")) != record.client_id
        or str(client.get("firm_id")) != record.firm_id
    ):
        raise SecureUploadTokenError(404, "Upload link not found")
    firm = await store.get_row("firms", record.firm_id)
    if not firm:
        raise SecureUploadTokenError(404, "Upload link not found")

    session = None
    application_session_id = application.get("demo_session_id")
    if record.demo_session_id or application_session_id:
        if str(record.demo_session_id or "") != str(application_session_id or ""):
            raise SecureUploadTokenError(404, "Upload link not found")
        session = await store.get_row("whatsapp_demo_sessions", str(record.demo_session_id))
        if (
            not session
            or session.get("status") != "active"
            or str(session.get("firm_id")) != record.firm_id
            or str(session.get("base_client_id")) != record.client_id
            or str(session.get("session_application_id")) != record.application_id
            or _parse_datetime(session["expires_at"]) <= datetime.now(UTC)
        ):
            raise SecureUploadTokenError(410, "Upload link has expired or was revoked")
    checklist = await store.list_rows(
        "document_requirements", {"application_id": record.application_id}, order="label"
    )
    if record.requirement_id and not any(
        str(row["id"]) == record.requirement_id for row in checklist
    ):
        raise SecureUploadTokenError(404, "Upload link not found")
    return ResolvedUploadContext(link, firm, client, application, session, checklist)


async def public_upload_context(
    store: DataStore,
    context: ResolvedUploadContext,
) -> dict[str, Any]:
    documents = await store.list_rows(
        "documents", {"application_id": context.application["id"]}, order="created_at", desc=True
    )
    link_documents = [
        document
        for document in documents
        if str(document.get("upload_link_id") or "") == str(context.link["id"])
    ]
    batches = await store.list_rows(
        "document_submission_batches",
        {"upload_link_id": context.link["id"]},
        order="submitted_at",
        desc=True,
        limit=1,
    )
    latest_batch = None
    if batches:
        batch = batches[0]
        latest_batch = {
            key: batch.get(key)
            for key in (
                "id",
                "status",
                "document_count",
                "completed_count",
                "failed_count",
                "submitted_at",
                "completed_at",
            )
        }
    latest_by_requirement: dict[str, dict[str, Any]] = {}
    for document in documents:
        requirement_id = document.get("requirement_id")
        if requirement_id and str(requirement_id) not in latest_by_requirement:
            latest_by_requirement[str(requirement_id)] = document
    checklist = []
    for requirement in context.checklist:
        document = latest_by_requirement.get(str(requirement["id"]))
        checklist.append(
            {
                "id": requirement["id"],
                "requirement_type": requirement.get("requirement_type"),
                "label": requirement["label"],
                "required": requirement.get("required", True),
                "status": requirement["status"],
                "upload_status": "uploaded" if document else "pending",
                "processing_status": document.get("processing_status") if document else None,
            }
        )
    return {
        "firm": {"name": context.firm["name"]},
        "client": {"business_name": context.client["business_name"]},
        "application": {
            "period_label": context.application["period_label"],
            "due_date": context.application.get("due_date"),
        },
        "checklist": checklist,
        "ready_to_submit_count": sum(
            document.get("processing_status") == "awaiting_submission"
            and not document.get("submission_batch_id")
            for document in link_documents
        ),
        "latest_submission_batch": latest_batch,
    }


async def store_secure_document(
    store: DataStore,
    settings: Settings,
    *,
    context: ResolvedUploadContext,
    requirement_id: str,
    filename: str,
    declared_mime_type: str,
    content: bytes,
) -> dict[str, Any]:
    async def audit_rejection(action: str, reason: str) -> None:
        await record_audit(
            store,
            firm_id=context.application["firm_id"],
            user_id=None,
            action=action,
            entity_type="upload_link",
            entity_id=context.link.get("id"),
            client_id=context.client["id"],
            application_id=context.application["id"],
            demo_session_id=context.application.get("demo_session_id"),
            metadata={"reason": reason},
        )

    try:
        validated = validate_secure_upload(
            settings,
            filename=filename,
            declared_mime_type=declared_mime_type,
            content=content,
        )
    except SecureUploadValidationError as exc:
        await audit_rejection("upload_unsupported_rejected", exc.code)
        raise
    requirement = next(
        (row for row in context.checklist if str(row["id"]) == str(requirement_id)),
        None,
    )
    if not requirement or (
        context.link.get("requirement_id")
        and str(context.link["requirement_id"]) != str(requirement_id)
    ):
        await audit_rejection("upload_failed", "requirement_mismatch")
        raise SecureUploadValidationError(
            "requirement_mismatch", "The selected checklist category is not available"
        )
    duplicates = await store.list_rows(
        "documents",
        {
            "application_id": context.application["id"],
            "sha256": validated.sha256,
        },
    )
    if any(row.get("processing_status") != "upload_failed" for row in duplicates):
        await audit_rejection("upload_duplicate_rejected", "duplicate")
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
    await record_audit(
        store,
        firm_id=context.application["firm_id"],
        user_id=None,
        action="upload_started",
        entity_type="document",
        entity_id=document_id,
        client_id=context.client["id"],
        application_id=context.application["id"],
        demo_session_id=context.application.get("demo_session_id"),
        metadata={"requirement_id": requirement["id"]},
    )
    uploaded = False
    finalized = False
    try:
        await store.upload_file(
            settings.supabase_documents_bucket,
            storage_path,
            content,
            validated.mime_type,
        )
        uploaded = True
        completed_at = datetime.now(UTC).isoformat()
        rows = await store.rpc(
            "complete_secure_document_upload",
            {
                "p_document_id": document_id,
                "p_firm_id": context.application["firm_id"],
                "p_client_id": context.client["id"],
                "p_application_id": context.application["id"],
                "p_demo_session_id": context.application.get("demo_session_id"),
                "p_requirement_id": requirement["id"],
                "p_original_name": validated.original_name,
                "p_safe_name": validated.safe_name,
                "p_mime_type": validated.mime_type,
                "p_file_size": validated.file_size,
                "p_sha256": validated.sha256,
                "p_storage_bucket": settings.supabase_documents_bucket,
                "p_storage_path": storage_path,
                "p_completed_at": completed_at,
            },
        )
        if not rows:
            raise RuntimeError("Secure upload could not be finalized")
        document = rows[0]
        document = (
            await store.update_row(
                "documents",
                document_id,
                {
                    "processing_status": "awaiting_submission",
                    "upload_link_id": context.link["id"],
                    "submission_batch_id": None,
                    "submitted_at": None,
                },
            )
            or document
        )
        finalized = True
        await record_audit(
            store,
            firm_id=context.application["firm_id"],
            user_id=None,
            action="upload_completed",
            entity_type="document",
            entity_id=document_id,
            client_id=context.client["id"],
            application_id=context.application["id"],
            demo_session_id=context.application.get("demo_session_id"),
            after_data={
                "requirement_id": requirement["id"],
                "processing_status": "awaiting_submission",
            },
        )
        await record_audit(
            store,
            firm_id=context.application["firm_id"],
            user_id=None,
            action="checklist_requirement_received",
            entity_type="document_requirement",
            entity_id=requirement["id"],
            client_id=context.client["id"],
            application_id=context.application["id"],
            demo_session_id=context.application.get("demo_session_id"),
            after_data={"status": "received", "document_id": document_id},
        )
        return document
    except Exception:
        if uploaded and not finalized:
            await store.delete_file(settings.supabase_documents_bucket, storage_path)
        if not finalized:
            await record_audit(
                store,
                firm_id=context.application["firm_id"],
                user_id=None,
                action="upload_failed",
                entity_type="document",
                entity_id=document_id,
                client_id=context.client["id"],
                application_id=context.application["id"],
                demo_session_id=context.application.get("demo_session_id"),
            )
        raise


@dataclass(frozen=True, slots=True)
class CreatedUploadLink:
    id: str
    raw_token: str
    upload_url: str
    expires_at: str


async def create_secure_upload_link(
    store: DataStore,
    settings: Settings,
    *,
    application: dict[str, Any],
    demo_session: dict[str, Any] | None = None,
    requirement_id: str | None = None,
    created_by_user_id: str | None = None,
) -> CreatedUploadLink:
    demo_session_id = application.get("demo_session_id")
    if demo_session_id:
        if (
            not demo_session
            or str(demo_session.get("id")) != str(demo_session_id)
            or str(demo_session.get("session_application_id"))
            != str(application.get("id"))
        ):
            raise ValueError("Demo upload link context does not match the session")
    elif demo_session is not None:
        raise ValueError("Normal applications cannot be bound to a demo session")

    raw_token, record = issue_upload_token(
        firm_id=application["firm_id"],
        application_id=application["id"],
        client_id=application["client_id"],
        demo_session_id=demo_session_id,
        requirement_id=requirement_id,
        pepper=settings.upload_token_pepper,
        ttl=timedelta(hours=settings.upload_link_ttl_hours),
    )
    row = await store.insert_row(
        "upload_links",
        {
            "firm_id": record.firm_id,
            "application_id": record.application_id,
            "client_id": record.client_id,
            "demo_session_id": record.demo_session_id,
            "requirement_id": record.requirement_id,
            "created_by_user_id": created_by_user_id,
            "token_hash": record.token_hash,
            "expires_at": record.expires_at.isoformat(),
            "revoked_at": None,
        },
    )
    upload_url = f"{settings.frontend_url.rstrip('/')}/upload/{raw_token}"
    await record_audit(
        store,
        firm_id=record.firm_id,
        user_id=created_by_user_id,
        action="upload_link_created",
        entity_type="upload_link",
        entity_id=row["id"],
        client_id=record.client_id,
        application_id=record.application_id,
        demo_session_id=record.demo_session_id,
        metadata={"expires_at": record.expires_at.isoformat()},
    )
    return CreatedUploadLink(
        id=str(row["id"]),
        raw_token=raw_token,
        upload_url=upload_url,
        expires_at=record.expires_at.isoformat(),
    )
