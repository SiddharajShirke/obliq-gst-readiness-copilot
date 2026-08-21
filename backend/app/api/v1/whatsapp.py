from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import Response

from app.agents.reminder_workflow import create_reminder_draft
from app.config import Settings, get_settings
from app.dependencies import current_user, require_firm_row, require_roles
from app.repositories import DataStore, get_store
from app.schemas.auth import UserContext
from app.schemas.whatsapp import ReminderApproval
from app.services.audit import record_audit
from app.services.upload_tokens import issue_upload_token
from app.services.whatsapp.base import WhatsAppSendError
from app.services.whatsapp.cleanup import cleanup_demo_sessions
from app.services.whatsapp.conversation import (
    MEDIA_PHASE_MESSAGE,
    build_welcome_message,
    handle_text_command,
)
from app.services.whatsapp.factory import get_whatsapp_provider
from app.services.whatsapp.rate_limit import rate_limiter
from app.services.whatsapp.security import PhoneProtector, mask_phone
from app.services.whatsapp.sessions import (
    bind_demo_session,
    cancel_demo_session,
    create_demo_session,
    find_active_session_by_phone,
    regenerate_start_token,
    verify_dashboard_access,
)

router = APIRouter(tags=["whatsapp"])
START_PATTERN = re.compile(r"^START OBLIQ DEMO ([ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8,10})$", re.I)
INVALID_SESSION_MESSAGE = (
    "This OBLIQ WhatsApp demo session is invalid or has expired.\n\n"
    "Return to the OBLIQ dashboard and generate a new session."
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _acknowledge() -> Response:
    return Response(status_code=200)


def _callback_url(settings: Settings) -> str:
    return (
        f"{settings.public_base_url.rstrip('/')}{settings.api_v1_prefix}"
        "/webhooks/vonage/status"
    )


def _protector(settings: Settings) -> PhoneProtector:
    return PhoneProtector(
        hash_pepper=settings.whatsapp_phone_hash_pepper,
        encryption_key=settings.whatsapp_phone_encryption_key,
    )


def _validate_request(
    request: Request,
    settings: Settings,
    raw_body: bytes,
) -> None:
    provider = get_whatsapp_provider(settings)
    if not provider.validate_webhook(
        raw_body=raw_body,
        authorization=request.headers.get("authorization"),
    ):
        raise HTTPException(status_code=403, detail="Invalid Vonage webhook signature")


async def _send_text(
    store: DataStore,
    settings: Settings,
    *,
    recipient: str,
    text: str,
    session: dict | None,
) -> None:
    session_id = str(session["id"]) if session else "unbound"
    if not rate_limiter.allow(
        f"outbound:{session_id}", limit=40, window_seconds=60
    ):
        return
    protector = _protector(settings)
    recipient_phone = protector.protect(recipient)
    provider = get_whatsapp_provider(settings)
    now = _now()
    try:
        result = await provider.send_text(
            recipient=recipient,
            text=text,
            status_callback=_callback_url(settings),
        )
        timestamps = {
            "queued_at": now if result.initial_status == "queued" else None,
            "sent_at": now if result.initial_status == "sent" else None,
            "delivered_at": now if result.initial_status == "delivered" else None,
        }
        await store.insert_row(
            "whatsapp_messages",
            {
                "firm_id": session.get("firm_id") if session else None,
                "client_id": session.get("base_client_id") if session else None,
                "application_id": (
                    session.get("session_application_id") if session else None
                ),
                "demo_session_id": session.get("id") if session else None,
                "provider": result.provider,
                "provider_message_id": result.provider_message_id,
                "direction": "outbound",
                "message_type": "text",
                "content": text,
                "delivery_status": result.initial_status,
                "recipient_phone_encrypted": recipient_phone.encrypted,
                "recipient_phone_last_four": recipient_phone.last_four,
                "metadata": {"temporary_demo": session is None},
                **timestamps,
            },
        )
        if session:
            await store.update_row(
                "whatsapp_demo_sessions",
                session["id"],
                {"last_activity_at": now},
            )
    except RuntimeError as exc:
        error_code = None
        error_message = "Vonage WhatsApp message could not be sent"
        if isinstance(exc, WhatsAppSendError):
            error_code = exc.code
            error_message = exc.safe_message
        await store.insert_row(
            "whatsapp_messages",
            {
                "firm_id": session.get("firm_id") if session else None,
                "client_id": session.get("base_client_id") if session else None,
                "application_id": (
                    session.get("session_application_id") if session else None
                ),
                "demo_session_id": session.get("id") if session else None,
                "provider": "vonage",
                "provider_message_id": None,
                "direction": "outbound",
                "message_type": "text",
                "content": text,
                "delivery_status": "failed",
                "error_code": error_code,
                "error_message": error_message,
                "recipient_phone_encrypted": recipient_phone.encrypted,
                "recipient_phone_last_four": recipient_phone.last_four,
                "failed_at": now,
                "metadata": {"temporary_demo": session is None},
            },
        )


async def _save_inbound(
    store: DataStore,
    settings: Settings,
    payload: dict[str, Any],
    session: dict | None,
) -> dict:
    protector = _protector(settings)
    sender = protector.protect(str(payload["from"]))
    recipient = protector.protect(
        str(payload.get("to") or settings.vonage_whatsapp_from)
    )
    provider_message_type = str(payload.get("message_type") or "text").lower()
    media_present = provider_message_type != "text"
    text = payload.get("text")
    return await store.insert_row(
        "whatsapp_messages",
        {
            "firm_id": session.get("firm_id") if session else None,
            "client_id": session.get("base_client_id") if session else None,
            "application_id": session.get("session_application_id") if session else None,
            "demo_session_id": session.get("id") if session else None,
            "provider": "vonage",
            "provider_message_id": payload["message_uuid"],
            "direction": "inbound",
            "message_type": "media" if media_present else "text",
            "content": text if isinstance(text, str) and text else None,
            "delivery_status": "received",
            "sender_phone_encrypted": sender.encrypted,
            "sender_phone_last_four": sender.last_four,
            "recipient_phone_encrypted": recipient.encrypted,
            "recipient_phone_last_four": recipient.last_four,
            "metadata": {
                "media_present": media_present,
                "provider_message_type": provider_message_type,
                "temporary_demo": session is None,
            },
        },
    )


async def _new_upload_link(
    store: DataStore,
    settings: Settings,
    application: dict[str, Any],
) -> str:
    raw, record = issue_upload_token(
        application_id=application["id"],
        client_id=application["client_id"],
        pepper=settings.upload_token_pepper,
        ttl=timedelta(hours=settings.upload_link_ttl_hours),
    )
    await store.insert_row(
        "upload_links",
        {
            "application_id": record.application_id,
            "client_id": record.client_id,
            "token_hash": record.token_hash,
            "expires_at": record.expires_at.isoformat(),
            "revoked_at": None,
        },
    )
    return f"{settings.frontend_url}/upload/{raw}"


async def _draft(
    *,
    application_id: str,
    reminder_type: str,
    user: UserContext,
    store: DataStore,
    settings: Settings,
) -> dict[str, Any]:
    application = await require_firm_row(
        store, "applications", application_id, user.firm_id
    )
    client = await store.get_row("clients", application["client_id"])
    assert client is not None
    checklist = await store.list_rows(
        "document_requirements", {"application_id": application_id}, order="label"
    )
    upload_url = await _new_upload_link(store, settings, application)
    reminder = await create_reminder_draft(
        store,
        {
            "firm_id": user.firm_id,
            "client": client,
            "application": application,
            "checklist": checklist,
            "upload_url": upload_url,
            "reminder_type": reminder_type,
        },
    )
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
    protector = _protector(settings)
    recipient = protector.protect(client["whatsapp_phone"])
    provider = get_whatsapp_provider(settings)
    result = await provider.send_text(
        recipient=client["whatsapp_phone"],
        text=text,
        status_callback=_callback_url(settings),
    )
    now = _now()
    await store.insert_row(
        "whatsapp_messages",
        {
            "firm_id": user.firm_id,
            "client_id": client["id"],
            "application_id": reminder["application_id"],
            "demo_session_id": None,
            "provider": result.provider,
            "direction": "outbound",
            "message_type": "text",
            "content": text,
            "provider_message_id": result.provider_message_id,
            "recipient_phone_encrypted": recipient.encrypted,
            "recipient_phone_last_four": recipient.last_four,
            "delivery_status": result.initial_status,
            "queued_at": now if result.initial_status == "queued" else None,
            "sent_at": now if result.initial_status == "sent" else None,
            "metadata": {},
        },
    )
    updated = await store.update_row(
        "reminders",
        reminder_id,
        {
            "approved_message": text,
            "status": "sent",
            "approved_by": user.user_id,
            "approved_at": now,
            "sent_at": now,
            "provider": result.provider,
        },
    )
    if reminder["reminder_type"] == "initial_document_request":
        await store.update_row(
            "applications", reminder["application_id"], {"status": "documents_requested"}
        )
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="reminder.approved_and_sent",
        entity_type="reminder",
        entity_id=reminder_id,
        client_id=client["id"],
        application_id=reminder["application_id"],
        after_data={"provider": result.provider, "message_id": result.provider_message_id},
    )
    assert updated is not None
    return updated


@router.post("/applications/{application_id}/document-request/draft", status_code=201)
async def draft_document_request(
    application_id: str,
    user: Annotated[
        UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))
    ],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return await _draft(
        application_id=application_id,
        reminder_type="initial_document_request",
        user=user,
        store=store,
        settings=settings,
    )


@router.post("/applications/{application_id}/document-request/approve-send")
async def approve_document_request(
    application_id: str,
    payload: ReminderApproval,
    user: Annotated[
        UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))
    ],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    reminder = await store.get_row("reminders", payload.reminder_id)
    if not reminder or reminder.get("application_id") != application_id:
        raise HTTPException(status_code=404, detail="Reminder not found for this application")
    return await _approve_send(
        reminder_id=payload.reminder_id,
        message_override=payload.message,
        user=user,
        store=store,
        settings=settings,
    )


@router.post("/applications/{application_id}/reminders/draft", status_code=201)
async def draft_missing_document_reminder(
    application_id: str,
    user: Annotated[
        UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))
    ],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return await _draft(
        application_id=application_id,
        reminder_type="missing_document_reminder",
        user=user,
        store=store,
        settings=settings,
    )


@router.post("/reminders/{reminder_id}/approve-send")
async def approve_reminder(
    reminder_id: str,
    payload: ReminderApproval,
    user: Annotated[
        UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))
    ],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return await _approve_send(
        reminder_id=reminder_id,
        message_override=payload.message,
        user=user,
        store=store,
        settings=settings,
    )


@router.post("/reminders/{reminder_id}/cancel")
async def cancel_reminder(
    reminder_id: str,
    user: Annotated[
        UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))
    ],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    reminder = await store.get_row("reminders", reminder_id)
    if not reminder or reminder.get("firm_id") != user.firm_id:
        raise HTTPException(status_code=404, detail="Reminder not found")
    updated = await store.update_row("reminders", reminder_id, {"status": "cancelled"})
    assert updated is not None
    return updated


async def _authorized_session(
    session_id: str,
    access_token: str | None,
    user: UserContext,
    store: DataStore,
    settings: Settings,
) -> dict:
    session = await store.get_row("whatsapp_demo_sessions", session_id)
    if not session or session.get("firm_id") != user.firm_id:
        raise HTTPException(status_code=404, detail="WhatsApp demo session not found")
    if not access_token or not await verify_dashboard_access(
        store, settings, session_id, access_token
    ):
        raise HTTPException(status_code=403, detail="Invalid demo access token")
    return session


@router.post(
    "/applications/{application_id}/whatsapp-demo-sessions",
    status_code=status.HTTP_201_CREATED,
)
async def create_whatsapp_demo_session(
    application_id: str,
    request: Request,
    user: Annotated[
        UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))
    ],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    limiter_key = f"create:{user.user_id}:{request.client.host if request.client else 'unknown'}"
    if not rate_limiter.allow(limiter_key, limit=10, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many demo sessions")
    await cleanup_demo_sessions(store, settings)
    application = await require_firm_row(
        store, "applications", application_id, user.firm_id
    )
    if application.get("demo_session_id"):
        raise HTTPException(status_code=404, detail="Base application not found")
    client = await store.get_row("clients", application["client_id"])
    assert client is not None
    created = await create_demo_session(store, settings, application_id, user.user_id)
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="whatsapp_demo_session.created",
        entity_type="whatsapp_demo_session",
        entity_id=created.session_id,
        client_id=client["id"],
        application_id=created.session_application_id,
        demo_session_id=created.session_id,
        metadata={"base_application_id": application_id},
    )
    return {
        "session_id": created.session_id,
        "base_client_name": client["business_name"],
        "gst_period": application["period_label"],
        "status": "waiting_for_start",
        "token_expires_at": created.token_expires_at,
        "session_expires_at": created.session_expires_at,
        "sandbox_sender": settings.vonage_whatsapp_from.removeprefix("+"),
        "sandbox_join_message": created.sandbox_join_message,
        "sandbox_join_whatsapp_url": created.sandbox_join_whatsapp_url,
        "start_message": created.start_message,
        "start_whatsapp_url": created.start_whatsapp_url,
        "dashboard_access_token": created.dashboard_access_token,
    }


@router.get("/whatsapp-demo-sessions/{session_id}")
async def whatsapp_demo_session_status(
    session_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
    access_token: Annotated[
        str | None, Header(alias="X-OBLIQ-Demo-Access-Token")
    ] = None,
) -> dict:
    await cleanup_demo_sessions(store, settings)
    session = await _authorized_session(
        session_id, access_token, user, store, settings
    )
    application = await store.get_row("applications", session["session_application_id"])
    client = await store.get_row("clients", session["base_client_id"])
    assert application is not None and client is not None
    checklist = await store.list_rows(
        "document_requirements",
        {"application_id": application["id"]},
        order="label",
    )
    outbound = await store.list_rows(
        "whatsapp_messages",
        {"demo_session_id": session_id, "direction": "outbound"},
        order="created_at",
        desc=True,
        limit=1,
    )
    masked_phone = None
    if session.get("judge_phone_encrypted"):
        masked_phone = mask_phone(
            _protector(settings).decrypt(session["judge_phone_encrypted"])
        )
    return {
        "status": session["status"],
        "connection_status": "connected" if session["status"] == "active" else "waiting",
        "masked_phone": masked_phone,
        "client_name": client["business_name"],
        "gst_period": application["period_label"],
        "current_step": session.get("current_step"),
        "checklist": [
            {"id": row["id"], "label": row["label"], "status": row["status"]}
            for row in checklist
        ],
        "last_activity_at": session.get("last_activity_at"),
        "token_expires_at": session["token_expires_at"],
        "session_expires_at": session["expires_at"],
        "last_outbound_delivery_status": (
            outbound[0].get("delivery_status") if outbound else None
        ),
    }


@router.post("/whatsapp-demo-sessions/{session_id}/cancel")
async def cancel_whatsapp_demo_session(
    session_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
    access_token: Annotated[
        str | None, Header(alias="X-OBLIQ-Demo-Access-Token")
    ] = None,
) -> dict:
    await _authorized_session(session_id, access_token, user, store, settings)
    session = await cancel_demo_session(store, session_id)
    return {"status": session["status"] if session else "cancelled"}


@router.post("/whatsapp-demo-sessions/{session_id}/regenerate-start-token")
async def regenerate_whatsapp_demo_start_token(
    session_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
    access_token: Annotated[
        str | None, Header(alias="X-OBLIQ-Demo-Access-Token")
    ] = None,
) -> dict:
    await _authorized_session(session_id, access_token, user, store, settings)
    try:
        token = await regenerate_start_token(store, settings, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "start_message": token.start_message,
        "start_whatsapp_url": token.start_whatsapp_url,
        "token_expires_at": token.token_expires_at,
    }


@router.post("/webhooks/vonage/whatsapp")
async def receive_vonage_whatsapp(
    request: Request,
    background_tasks: BackgroundTasks,
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    raw_body = await request.body()
    _validate_request(request, settings, raw_body)
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid Vonage webhook payload") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid Vonage webhook payload")
    body_value = payload.get("text")
    body = body_value if isinstance(body_value, str) else ""
    sandbox_join_message = settings.vonage_sandbox_join_message.strip()
    if (
        sandbox_join_message
        and body.strip().casefold() == sandbox_join_message.casefold()
    ):
        return _acknowledge()
    message_uuid = payload.get("message_uuid")
    sender = payload.get("from")
    if not isinstance(message_uuid, str) or not isinstance(sender, str):
        return _acknowledge()
    duplicates = await store.list_rows(
        "whatsapp_messages",
        {"provider": "vonage", "provider_message_id": message_uuid},
        limit=1,
    )
    if duplicates:
        return _acknowledge()
    await cleanup_demo_sessions(store, settings)

    match = START_PATTERN.fullmatch(body.strip())
    if match:
        inbound = await _save_inbound(store, settings, payload, None)
        session = await bind_demo_session(
            store,
            settings,
            start_token=match.group(1).upper(),
            sender_phone=sender,
            provider_user_id=sender,
        )
        if not session:
            can_reply = rate_limiter.allow(
                f"invalid-start:{request.client.host if request.client else 'unknown'}",
                limit=20,
                window_seconds=60,
            )
            if not can_reply:
                return _acknowledge()
            background_tasks.add_task(
                _send_text,
                store,
                settings,
                recipient=sender,
                text=INVALID_SESSION_MESSAGE,
                session=None,
            )
            return _acknowledge()
        await store.update_row(
            "whatsapp_messages",
            inbound["id"],
            {
                "firm_id": session["firm_id"],
                "client_id": session["base_client_id"],
                "application_id": session["session_application_id"],
                "demo_session_id": session["id"],
            },
        )
        await record_audit(
            store,
            firm_id=session["firm_id"],
            user_id=None,
            action="whatsapp_demo_session.bound",
            entity_type="whatsapp_demo_session",
            entity_id=session["id"],
            client_id=session["base_client_id"],
            application_id=session["session_application_id"],
            demo_session_id=session["id"],
        )
        welcome = await build_welcome_message(store, session)
        background_tasks.add_task(
            _send_text,
            store,
            settings,
            recipient=sender,
            text=welcome,
            session=session,
        )
        return _acknowledge()

    session = await find_active_session_by_phone(store, settings, sender)
    await _save_inbound(store, settings, payload, session)
    if not session:
        background_tasks.add_task(
            _send_text,
            store,
            settings,
            recipient=sender,
            text=INVALID_SESSION_MESSAGE,
            session=None,
        )
        return _acknowledge()

    if str(payload.get("message_type") or "text").lower() != "text":
        reply_text = MEDIA_PHASE_MESSAGE
    else:
        reply = await handle_text_command(store, session, body)
        reply_text = reply.text
        if reply.action == "cancel":
            await cancel_demo_session(store, session["id"])
        elif reply.action == "escalate":
            await record_audit(
                store,
                firm_id=session["firm_id"],
                user_id=None,
                action="whatsapp.tax_question_escalated",
                entity_type="whatsapp_demo_session",
                entity_id=session["id"],
                client_id=session["base_client_id"],
                application_id=session["session_application_id"],
                demo_session_id=session["id"],
                metadata={"channel": "whatsapp", "requires_ca_review": True},
            )
    background_tasks.add_task(
        _send_text,
        store,
        settings,
        recipient=sender,
        text=reply_text,
        session=session,
    )
    return _acknowledge()


@router.post("/webhooks/vonage/status")
async def receive_vonage_status(
    request: Request,
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    raw_body = await request.body()
    _validate_request(request, settings, raw_body)
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid Vonage webhook payload") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid Vonage webhook payload")
    message_uuid = payload.get("message_uuid")
    provider_status = str(payload.get("status") or "").lower()
    message_status = {
        "accepted": "queued",
        "submitted": "sent",
        "delivered": "delivered",
        "read": "read",
        "rejected": "failed",
        "undeliverable": "failed",
    }.get(provider_status)
    if not isinstance(message_uuid, str) or not message_status:
        return _acknowledge()
    rows = await store.list_rows(
        "whatsapp_messages",
        {"provider": "vonage", "provider_message_id": message_uuid},
        limit=1,
    )
    if not rows:
        return _acknowledge()
    timestamp_column = {
        "queued": "queued_at",
        "sent": "sent_at",
        "delivered": "delivered_at",
        "read": "read_at",
        "failed": "failed_at",
    }.get(message_status)
    error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
    changes: dict[str, Any] = {
        "delivery_status": message_status,
        "error_code": str(error.get("title")) if error.get("title") is not None else None,
        "error_message": error.get("detail") if isinstance(error.get("detail"), str) else None,
    }
    if timestamp_column and not rows[0].get(timestamp_column):
        changes[timestamp_column] = _now()
    await store.update_row("whatsapp_messages", rows[0]["id"], changes)
    return _acknowledge()


@router.get("/integrations/whatsapp/status")
async def whatsapp_integration_status(
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    inbound = await store.list_rows(
        "whatsapp_messages",
        {"firm_id": user.firm_id, "direction": "inbound"},
        order="created_at",
        desc=True,
        limit=1,
    )
    successful = await store.list_rows(
        "whatsapp_messages",
        {"firm_id": user.firm_id, "direction": "outbound"},
        order="created_at",
        desc=True,
        limit=1,
    )
    base = settings.public_base_url.rstrip("/")
    return {
        "provider": "Vonage Messages API Sandbox",
        "configuration": "Ready" if settings.whatsapp_provider == "vonage" else "Test",
        "sandbox_sender": settings.vonage_whatsapp_from.removeprefix("+"),
        "inbound_webhook_url": (
            f"{base}{settings.api_v1_prefix}/webhooks/vonage/whatsapp"
        ),
        "status_callback_url": _callback_url(settings),
        "public_base_url": settings.public_base_url,
        "last_webhook_time": inbound[0]["created_at"] if inbound else None,
        "last_successful_message": successful[0]["created_at"] if successful else None,
    }
