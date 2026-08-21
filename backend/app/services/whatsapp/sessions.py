from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from app.config import Settings
from app.repositories.base import DataStore
from app.services.whatsapp.security import (
    PhoneProtector,
    generate_dashboard_token,
    generate_start_token,
    hash_demo_token,
)


@dataclass(frozen=True, slots=True)
class CreatedDemoSession:
    session_id: str
    session_application_id: str
    start_token: str
    dashboard_access_token: str
    sandbox_join_message: str
    sandbox_join_whatsapp_url: str
    start_message: str
    start_whatsapp_url: str
    token_expires_at: str
    session_expires_at: str


@dataclass(frozen=True, slots=True)
class RegeneratedStartToken:
    start_token: str
    start_message: str
    start_whatsapp_url: str
    token_expires_at: str


def _now() -> datetime:
    return datetime.now(UTC)


def _sender_digits(settings: Settings) -> str:
    digits = "".join(
        character
        for character in settings.vonage_whatsapp_from
        if character.isdigit()
    )
    if not digits:
        raise RuntimeError("VONAGE_WHATSAPP_FROM is not configured")
    return digits


def _whatsapp_url(settings: Settings, message: str) -> str:
    return f"https://wa.me/{_sender_digits(settings)}?text={quote(message, safe='')}"


async def create_demo_session(
    store: DataStore,
    settings: Settings,
    base_application_id: str,
    created_by_user_id: str,
) -> CreatedDemoSession:
    base = await store.get_row("applications", base_application_id)
    if not base or base.get("demo_session_id"):
        raise ValueError("Base GST application was not found")
    start_token = generate_start_token()
    dashboard_token = generate_dashboard_token()
    now = _now()
    token_expires = now + timedelta(minutes=settings.whatsapp_demo_token_expiry_minutes)
    session_expires = now + timedelta(minutes=settings.whatsapp_demo_session_expiry_minutes)
    rows = await store.rpc(
        "create_whatsapp_demo_session",
        {
            "p_firm_id": base["firm_id"],
            "p_base_application_id": base_application_id,
            "p_created_by_user_id": created_by_user_id,
            "p_start_token_hash": hash_demo_token(
                start_token, pepper=settings.whatsapp_demo_token_pepper, domain="start"
            ),
            "p_dashboard_access_token_hash": hash_demo_token(
                dashboard_token,
                pepper=settings.whatsapp_demo_token_pepper,
                domain="dashboard",
            ),
            "p_token_expires_at": token_expires.isoformat(),
            "p_expires_at": session_expires.isoformat(),
        },
    )
    if not rows:
        raise RuntimeError("Demo session could not be created")
    row = rows[0]
    start_message = f"START OBLIQ DEMO {start_token}"
    return CreatedDemoSession(
        session_id=str(row["session_id"]),
        session_application_id=str(row["session_application_id"]),
        start_token=start_token,
        dashboard_access_token=dashboard_token,
        sandbox_join_message=settings.vonage_sandbox_join_message,
        sandbox_join_whatsapp_url=_whatsapp_url(
            settings, settings.vonage_sandbox_join_message
        ),
        start_message=start_message,
        start_whatsapp_url=_whatsapp_url(settings, start_message),
        token_expires_at=token_expires.isoformat(),
        session_expires_at=session_expires.isoformat(),
    )


async def verify_dashboard_access(
    store: DataStore,
    settings: Settings,
    session_id: str,
    raw_token: str,
) -> bool:
    session = await store.get_row("whatsapp_demo_sessions", session_id)
    if not session or not raw_token:
        return False
    supplied = hash_demo_token(
        raw_token,
        pepper=settings.whatsapp_demo_token_pepper,
        domain="dashboard",
    )
    return hmac.compare_digest(str(session["dashboard_access_token_hash"]), supplied)


async def regenerate_start_token(
    store: DataStore,
    settings: Settings,
    session_id: str,
) -> RegeneratedStartToken:
    session = await store.get_row("whatsapp_demo_sessions", session_id)
    if (
        not session
        or session.get("status") != "waiting_for_start"
        or session.get("judge_phone_hash")
    ):
        raise ValueError("START token cannot be regenerated for this session")
    token = generate_start_token()
    expires = _now() + timedelta(minutes=settings.whatsapp_demo_token_expiry_minutes)
    await store.update_row(
        "whatsapp_demo_sessions",
        session_id,
        {
            "start_token_hash": hash_demo_token(
                token, pepper=settings.whatsapp_demo_token_pepper, domain="start"
            ),
            "token_expires_at": expires.isoformat(),
        },
    )
    message = f"START OBLIQ DEMO {token}"
    return RegeneratedStartToken(
        start_token=token,
        start_message=message,
        start_whatsapp_url=_whatsapp_url(settings, message),
        token_expires_at=expires.isoformat(),
    )


async def bind_demo_session(
    store: DataStore,
    settings: Settings,
    *,
    start_token: str,
    sender_phone: str,
    provider_user_id: str | None,
) -> dict | None:
    protector = PhoneProtector(
        hash_pepper=settings.whatsapp_phone_hash_pepper,
        encryption_key=settings.whatsapp_phone_encryption_key,
    )
    protected = protector.protect(sender_phone)
    rows = await store.rpc(
        "bind_whatsapp_demo_session",
        {
            "p_start_token_hash": hash_demo_token(
                start_token, pepper=settings.whatsapp_demo_token_pepper, domain="start"
            ),
            "p_judge_phone_hash": protected.lookup_hash,
            "p_judge_phone_encrypted": protected.encrypted,
            "p_judge_phone_last_four": protected.last_four,
            "p_provider_user_id_hash": (
                hash_demo_token(
                    provider_user_id,
                    pepper=settings.whatsapp_phone_hash_pepper,
                    domain="provider-user",
                )
                if provider_user_id
                else None
            ),
            "p_now": _now().isoformat(),
        },
    )
    return rows[0] if rows else None


async def cancel_demo_session(store: DataStore, session_id: str) -> dict | None:
    session = await store.get_row("whatsapp_demo_sessions", session_id)
    if not session or session.get("status") in {"expired", "cancelled", "completed"}:
        return session
    now = _now().isoformat()
    return await store.update_row(
        "whatsapp_demo_sessions",
        session_id,
        {"status": "cancelled", "cancelled_at": now, "last_activity_at": now},
    )


async def find_active_session_by_phone(
    store: DataStore,
    settings: Settings,
    sender_phone: str,
) -> dict | None:
    protector = PhoneProtector(
        hash_pepper=settings.whatsapp_phone_hash_pepper,
        encryption_key=settings.whatsapp_phone_encryption_key,
    )
    phone_hash = protector.protect(sender_phone).lookup_hash
    rows = await store.list_rows(
        "whatsapp_demo_sessions",
        {"judge_phone_hash": phone_hash, "status": "active"},
        order="connected_at",
        desc=True,
        limit=1,
    )
    return rows[0] if rows else None
