from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse

from app.agents.reminder_workflow import create_reminder_draft
from app.config import Settings, get_settings
from app.dependencies import current_user, require_firm_row, require_roles
from app.repositories import DataStore, get_store
from app.schemas.auth import UserContext
from app.schemas.whatsapp import DemoInboundMessage, MetaCredentialsInput, ReminderApproval, WhatsAppTestRequest
from app.services.audit import record_audit
from app.services.document_processing.classifier import classify_document
from app.services.document_processing.processor import persist_uploaded_document
from app.services.upload_tokens import issue_upload_token
from app.services.whatsapp.factory import get_whatsapp_provider, load_meta_credentials
from app.services.whatsapp.meta import normalize_phone, parse_webhook_payload
from app.services.whatsapp.security import verify_meta_signature

router = APIRouter(tags=["whatsapp"])


async def _new_upload_link(store: DataStore, settings: Settings, application: dict[str, Any]) -> str:
    raw, record = issue_upload_token(
        application_id=application["id"],
        client_id=application["client_id"],
        pepper=settings.upload_token_pepper,
        ttl=timedelta(hours=settings.upload_link_ttl_hours),
    )
    await store.insert_row("upload_links", {
        "application_id": record.application_id,
        "client_id": record.client_id,
        "token_hash": record.token_hash,
        "expires_at": record.expires_at.isoformat(),
        "revoked_at": None,
    })
    return f"{settings.frontend_url}/upload/{raw}"


async def _draft(
    *,
    application_id: str,
    reminder_type: str,
    user: UserContext,
    store: DataStore,
    settings: Settings,
) -> dict[str, Any]:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    client = await store.get_row("clients", application["client_id"])
    assert client is not None
    checklist = await store.list_rows("document_requirements", {"application_id": application_id}, order="label")
    upload_url = await _new_upload_link(store, settings, application)
    reminder = await create_reminder_draft(store, {
        "firm_id": user.firm_id,
        "client": client,
        "application": application,
        "checklist": checklist,
        "upload_url": upload_url,
        "reminder_type": reminder_type,
    })
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="reminder.drafted",
        entity_type="reminder",
        entity_id=reminder["id"],
        client_id=client["id"],
        application_id=application_id,
        after_data={"type": reminder_type},
    )
    return {**reminder, "upload_url": upload_url}


async def _approve_send(
    *,
    reminder_id: str,
    message_override: str | None,
    user: UserContext,
    store: DataStore,
    settings: Settings,
) -> dict[str, Any]:
    reminder = await store.get_row("reminders", reminder_id)
    if not reminder or reminder.get("firm_id") != user.firm_id:
        raise HTTPException(status_code=404, detail="Reminder not found")
    if reminder.get("status") not in {"draft", "awaiting_approval", "approved"}:
        raise HTTPException(status_code=409, detail="Reminder is not awaiting approval")
    client = await store.get_row("clients", reminder["client_id"])
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if not client.get("whatsapp_consent"):
        raise HTTPException(
            status_code=409,
            detail="Client WhatsApp consent is required before sending an outbound message",
        )
    text = message_override or reminder["draft_message"]
    provider = get_whatsapp_provider(settings)
    result = await provider.send_text(recipient=client["whatsapp_phone"], text=text)
    await store.insert_row("whatsapp_messages", {
        "firm_id": user.firm_id,
        "client_id": client["id"],
        "application_id": reminder["application_id"],
        "provider": provider.name,
        "direction": "outbound",
        "message_type": "text",
        "content": text,
        "external_message_id": result.external_message_id,
        "sender_phone": settings.meta_phone_number_id if provider.name == "meta" else "OBLIQ-DEMO",
        "recipient_phone": client["whatsapp_phone"],
        "delivery_status": result.status,
        "metadata": result.raw,
    })
    updated = await store.update_row("reminders", reminder_id, {
        "approved_message": text,
        "status": "sent",
        "approved_by": user.user_id,
        "approved_at": datetime.now(UTC).isoformat(),
        "sent_at": datetime.now(UTC).isoformat(),
        "provider": provider.name,
    })
    if reminder["reminder_type"] == "initial_document_request":
        await store.update_row("applications", reminder["application_id"], {"status": "documents_requested"})
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="reminder.approved_and_sent",
        entity_type="reminder",
        entity_id=reminder_id,
        client_id=client["id"],
        application_id=reminder["application_id"],
        after_data={"provider": provider.name, "message_id": result.external_message_id},
    )
    assert updated is not None
    return updated


@router.post("/applications/{application_id}/document-request/draft", status_code=201)
async def draft_document_request(
    application_id: str,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return await _draft(application_id=application_id, reminder_type="initial_document_request", user=user, store=store, settings=settings)


@router.post("/applications/{application_id}/document-request/approve-send")
async def approve_document_request(
    application_id: str,
    payload: ReminderApproval,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    reminder = await store.get_row("reminders", payload.reminder_id)
    if not reminder or reminder.get("application_id") != application_id:
        raise HTTPException(status_code=404, detail="Reminder not found for this application")
    return await _approve_send(reminder_id=payload.reminder_id, message_override=payload.message, user=user, store=store, settings=settings)


@router.post("/applications/{application_id}/reminders/draft", status_code=201)
async def draft_missing_document_reminder(
    application_id: str,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return await _draft(application_id=application_id, reminder_type="missing_document_reminder", user=user, store=store, settings=settings)


@router.post("/reminders/{reminder_id}/approve-send")
async def approve_reminder(
    reminder_id: str,
    payload: ReminderApproval,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return await _approve_send(reminder_id=reminder_id, message_override=payload.message, user=user, store=store, settings=settings)


@router.post("/reminders/{reminder_id}/cancel")
async def cancel_reminder(
    reminder_id: str,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    reminder = await store.get_row("reminders", reminder_id)
    if not reminder or reminder.get("firm_id") != user.firm_id:
        raise HTTPException(status_code=404, detail="Reminder not found")
    updated = await store.update_row("reminders", reminder_id, {"status": "cancelled"})
    assert updated is not None
    return updated


@router.get("/demo/messages")
async def demo_messages(
    client_id: str | None = None,
    application_id: str | None = None,
    store: DataStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    if not settings.demo_mode:
        raise HTTPException(status_code=404, detail="Demo client is disabled")
    filters = {key: value for key, value in {"client_id": client_id, "application_id": application_id}.items() if value}
    return await store.list_rows("whatsapp_messages", filters, order="created_at")


@router.post("/demo/messages", status_code=201)
async def demo_inbound_message(
    payload: DemoInboundMessage,
    store: DataStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.demo_mode:
        raise HTTPException(status_code=404, detail="Demo client is disabled")
    client = await store.get_row("clients", payload.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    application_id = payload.application_id
    if not application_id:
        apps = await store.list_rows("applications", {"client_id": payload.client_id})
        active = [row for row in apps if row.get("status") != "completed"]
        application_id = active[0]["id"] if active else None
    return await store.insert_row("whatsapp_messages", {
        "firm_id": client["firm_id"],
        "client_id": client["id"],
        "application_id": application_id,
        "provider": "mock",
        "direction": "inbound",
        "message_type": "text",
        "content": payload.text,
        "external_message_id": f"mock-inbound-{datetime.now(UTC).timestamp()}",
        "sender_phone": client["whatsapp_phone"],
        "recipient_phone": "OBLIQ-DEMO",
        "delivery_status": "received",
        "metadata": {},
    })


@router.post("/demo/upload", status_code=201)
async def demo_upload(
    client_id: str = Form(...),
    requirement_type: str = Form(...),
    application_id: str | None = Form(None),
    file: UploadFile = File(...),
    store: DataStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.demo_mode:
        raise HTTPException(status_code=404, detail="Demo client is disabled")
    client = await store.get_row("clients", client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    apps = await store.list_rows("applications", {"client_id": client_id})
    application = next((row for row in apps if row["id"] == application_id), None) if application_id else next((row for row in apps if row.get("status") != "completed"), None)
    if not application:
        raise HTTPException(status_code=409, detail="No active GST application found")
    return await persist_uploaded_document(
        store,
        settings,
        application=application,
        client=client,
        filename=file.filename or "whatsapp-upload.bin",
        mime_type=file.content_type or "application/octet-stream",
        content=await file.read(),
        requirement_type=requirement_type,
        source="mock_whatsapp",
        uploaded_from_phone=client["whatsapp_phone"],
    )


@router.get("/webhooks/whatsapp", response_class=PlainTextResponse)
async def verify_whatsapp_webhook(
    mode: str = Query(alias="hub.mode"),
    verify_token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge"),
    settings: Settings = Depends(get_settings),
) -> str:
    credentials = load_meta_credentials(settings)
    expected = credentials.webhook_verify_token or settings.meta_webhook_verify_token
    if mode != "subscribe" or verify_token != expected:
        raise HTTPException(status_code=403, detail="Webhook verification failed")
    return challenge


@router.post("/webhooks/whatsapp")
async def receive_whatsapp_webhook(
    request: Request,
    store: DataStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    raw = await request.body()
    credentials = load_meta_credentials(settings)
    if credentials.app_secret and not verify_meta_signature(raw, request.headers.get("x-hub-signature-256"), credentials.app_secret):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")
    payload = json.loads(raw or b"{}")
    events = parse_webhook_payload(payload)
    provider = get_whatsapp_provider(settings)
    processed = 0
    for event in events:
        if event.kind == "status":
            rows = await store.list_rows("whatsapp_messages", {"external_message_id": event.external_message_id}, limit=1)
            if rows:
                await store.update_row("whatsapp_messages", rows[0]["id"], {"delivery_status": event.status or "sent"})
            processed += 1
            continue

        clients = await store.list_rows("clients")
        client = next((row for row in clients if normalize_phone(row.get("whatsapp_phone")) == event.sender_phone), None)
        if not client:
            await store.insert_row("whatsapp_messages", {
                "firm_id": None,
                "client_id": None,
                "application_id": None,
                "provider": "meta",
                "direction": "inbound",
                "message_type": event.message_type or "text",
                "content": event.text,
                "external_message_id": event.external_message_id,
                "sender_phone": event.sender_phone,
                "recipient_phone": credentials.phone_number_id,
                "delivery_status": "received",
                "metadata": {"needs_assignment": True, "raw": event.raw},
            })
            processed += 1
            continue
        applications = [row for row in await store.list_rows("applications", {"client_id": client["id"]}) if row.get("status") != "completed"]
        application = applications[0] if len(applications) == 1 else None
        message = await store.insert_row("whatsapp_messages", {
            "firm_id": client["firm_id"],
            "client_id": client["id"],
            "application_id": application.get("id") if application else None,
            "provider": "meta",
            "direction": "inbound",
            "message_type": event.message_type or "text",
            "content": event.text,
            "external_message_id": event.external_message_id,
            "sender_phone": event.sender_phone,
            "recipient_phone": credentials.phone_number_id,
            "delivery_status": "received",
            "metadata": {"needs_assignment": application is None, "raw": event.raw},
        })
        if event.media_id and application:
            content, mime_type, downloaded_name = await provider.download_media(event.media_id)
            filename = event.filename or downloaded_name
            detected = classify_document(filename, event.mime_type or mime_type, content)
            requirement_type = detected if detected != "unknown" else "purchase_invoice"
            document = await persist_uploaded_document(
                store,
                settings,
                application=application,
                client=client,
                filename=filename,
                mime_type=event.mime_type or mime_type,
                content=content,
                requirement_type=requirement_type,
                source="meta_whatsapp",
                uploaded_from_phone=event.sender_phone,
            )
            await store.update_row("whatsapp_messages", message["id"], {"media_document_id": document["id"]})
        processed += 1
    return {"received": len(events), "processed": processed}


@router.get("/integrations/whatsapp/status")
async def whatsapp_status(
    user: Annotated[UserContext, Depends(current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    credentials = load_meta_credentials(settings)
    base = settings.public_webhook_base_url or settings.backend_url
    return {
        "provider": settings.whatsapp_provider,
        "demo_mode": settings.demo_mode,
        "local_credential_setup_enabled": settings.allow_local_credential_setup,
        "meta_configured": bool(credentials.access_token and credentials.phone_number_id),
        "phone_number_id": credentials.phone_number_id or None,
        "waba_id": credentials.waba_id or None,
        "test_recipient": credentials.test_recipient_number or None,
        "webhook_url": f"{base.rstrip('/')}{settings.api_v1_prefix}/webhooks/whatsapp",
        "firm_id": user.firm_id,
    }


@router.post("/integrations/whatsapp/save-local")
async def save_local_meta_credentials(
    payload: MetaCredentialsInput,
    user: Annotated[UserContext, Depends(require_roles("firm_admin"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if not settings.allow_local_credential_setup:
        raise HTTPException(status_code=403, detail="Local credential setup is disabled in this environment")
    path = settings.local_meta_credentials_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload.model_dump(), indent=2), encoding="utf-8")
    os.chmod(path, 0o600)
    return {"message": "Credentials saved on this local backend only", "path": str(path), "firm_id": user.firm_id}


@router.post("/integrations/whatsapp/test")
async def test_whatsapp_connection(
    payload: WhatsAppTestRequest,
    user: Annotated[UserContext, Depends(require_roles("firm_admin"))],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    provider = get_whatsapp_provider(settings)
    credentials = load_meta_credentials(settings)
    recipient = payload.recipient or credentials.test_recipient_number
    if not recipient:
        raise HTTPException(status_code=400, detail="A verified test recipient number is required")
    result = await provider.send_text(recipient=recipient, text=payload.message)
    await store.upsert_row("integration_settings", {
        "firm_id": user.firm_id,
        "provider": provider.name,
        "phone_number_id": credentials.phone_number_id,
        "waba_id": credentials.waba_id,
        "test_recipient": recipient,
        "connection_status": "connected",
        "last_message_at": datetime.now(UTC).isoformat(),
    }, on_conflict="firm_id")
    return {"message_id": result.external_message_id, "status": result.status, "provider": provider.name}
