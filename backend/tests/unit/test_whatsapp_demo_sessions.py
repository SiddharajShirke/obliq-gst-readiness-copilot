from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from app.config import Settings
from app.repositories.memory import DEMO_ADMIN_ID, MemoryStore
from app.services.whatsapp.cleanup import cleanup_demo_sessions
from app.services.whatsapp.sessions import (
    bind_demo_session,
    cancel_demo_session,
    create_demo_session,
    regenerate_start_token,
    verify_dashboard_access,
)

APP_ID = "30000000-0000-0000-0000-000000000001"


def _settings() -> Settings:
    return Settings(
        app_env="test",
        whatsapp_provider="mock",
        whatsapp_demo_token_pepper="token-pepper",
        whatsapp_phone_hash_pepper="phone-pepper",
        whatsapp_phone_encryption_key=Fernet.generate_key().decode(),
        vonage_whatsapp_from="14155238886",
        vonage_sandbox_join_message="join obliq-demo",
        public_base_url="https://api.example.com",
        _env_file=None,
    )


@pytest.mark.asyncio
async def test_two_sessions_clone_application_and_checklist_without_touching_base() -> None:
    settings = _settings()
    store = MemoryStore(settings)
    base_before = await store.get_row("applications", APP_ID)
    base_checklist_before = await store.list_rows(
        "document_requirements", {"application_id": APP_ID}
    )

    first = await create_demo_session(store, settings, APP_ID, DEMO_ADMIN_ID)
    second = await create_demo_session(store, settings, APP_ID, DEMO_ADMIN_ID)

    assert first.session_id != second.session_id
    assert first.start_token != second.start_token
    assert first.session_application_id != second.session_application_id
    first_checklist = await store.list_rows(
        "document_requirements", {"application_id": first.session_application_id}
    )
    second_checklist = await store.list_rows(
        "document_requirements", {"application_id": second.session_application_id}
    )
    assert len(first_checklist) == len(second_checklist) == len(base_checklist_before) == 5
    assert {row["id"] for row in first_checklist}.isdisjoint(
        {row["id"] for row in second_checklist}
    )
    assert all(row["status"] == "missing" for row in first_checklist + second_checklist)
    assert await store.get_row("applications", APP_ID) == base_before


@pytest.mark.asyncio
async def test_dashboard_token_and_regenerated_start_token_are_single_session_secrets() -> None:
    settings = _settings()
    store = MemoryStore(settings)
    created = await create_demo_session(store, settings, APP_ID, DEMO_ADMIN_ID)

    assert await verify_dashboard_access(
        store, settings, created.session_id, created.dashboard_access_token
    )
    assert not await verify_dashboard_access(store, settings, created.session_id, "wrong")

    regenerated = await regenerate_start_token(store, settings, created.session_id)
    assert regenerated.start_token != created.start_token
    assert await bind_demo_session(
        store,
        settings,
        start_token=created.start_token,
        sender_phone="whatsapp:+919876543210",
        provider_user_id="919876543210",
    ) is None
    bound = await bind_demo_session(
        store,
        settings,
        start_token=regenerated.start_token,
        sender_phone="whatsapp:+919876543210",
        provider_user_id="919876543210",
    )
    assert bound is not None
    assert bound["status"] == "active"
    assert bound["start_token_hash"] is None
    assert bound["judge_phone_last_four"] == "3210"


@pytest.mark.asyncio
async def test_cancelled_session_cannot_bind_and_does_not_affect_another_session() -> None:
    settings = _settings()
    store = MemoryStore(settings)
    first = await create_demo_session(store, settings, APP_ID, DEMO_ADMIN_ID)
    second = await create_demo_session(store, settings, APP_ID, DEMO_ADMIN_ID)

    await cancel_demo_session(store, first.session_id)

    assert await bind_demo_session(
        store,
        settings,
        start_token=first.start_token,
        sender_phone="+919876543210",
        provider_user_id=None,
    ) is None
    assert (await store.get_row("whatsapp_demo_sessions", second.session_id))["status"] == (
        "waiting_for_start"
    )


@pytest.mark.asyncio
async def test_cleanup_anonymizes_expired_phone_and_deletes_only_retained_session_data() -> None:
    settings = _settings()
    store = MemoryStore(settings)
    created = await create_demo_session(store, settings, APP_ID, DEMO_ADMIN_ID)
    await bind_demo_session(
        store,
        settings,
        start_token=created.start_token,
        sender_phone="+919876543210",
        provider_user_id="919876543210",
    )
    old = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    await store.update_row(
        "whatsapp_demo_sessions",
        created.session_id,
        {"expires_at": old, "created_at": old},
    )
    await store.insert_row(
        "whatsapp_messages",
        {
            "demo_session_id": created.session_id,
            "provider": "vonage",
            "provider_message_id": "00000000-0000-4000-8000-000000000001",
        },
    )

    result = await cleanup_demo_sessions(store, settings)

    assert result == {"expired": 1, "deleted": 1}
    assert await store.get_row("whatsapp_demo_sessions", created.session_id) is None
    assert await store.get_row("applications", created.session_application_id) is None
    assert await store.get_row("applications", APP_ID) is not None
    assert not await store.list_rows(
        "whatsapp_messages", {"demo_session_id": created.session_id}
    )


@pytest.mark.asyncio
async def test_expiry_anonymizes_phone_before_retention_deletion() -> None:
    settings = _settings()
    store = MemoryStore(settings)
    created = await create_demo_session(store, settings, APP_ID, DEMO_ADMIN_ID)
    await bind_demo_session(
        store,
        settings,
        start_token=created.start_token,
        sender_phone="+919876543210",
        provider_user_id="919876543210",
    )
    await store.update_row(
        "whatsapp_demo_sessions",
        created.session_id,
        {"expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()},
    )

    result = await cleanup_demo_sessions(store, settings)
    session = await store.get_row("whatsapp_demo_sessions", created.session_id)

    assert result == {"expired": 1, "deleted": 0}
    assert session["status"] == "expired"
    assert session["judge_phone_hash"] is None
    assert session["judge_phone_encrypted"] is None
    assert session["provider_user_id_hash"] is None
    assert session["judge_phone_last_four"] == "3210"


@pytest.mark.asyncio
async def test_cleanup_removes_old_unbound_demo_attempts_but_keeps_normal_messages() -> None:
    settings = _settings()
    store = MemoryStore(settings)
    old = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    temporary = await store.insert_row(
        "whatsapp_messages",
        {
            "provider": "vonage",
            "provider_message_id": "00000000-0000-4000-8000-000000000002",
            "metadata": {"temporary_demo": True},
        },
    )
    normal = await store.insert_row(
        "whatsapp_messages",
        {
            "provider": "vonage",
            "provider_message_id": "00000000-0000-4000-8000-000000000003",
            "metadata": {},
        },
    )
    await store.update_row("whatsapp_messages", temporary["id"], {"created_at": old})
    await store.update_row("whatsapp_messages", normal["id"], {"created_at": old})

    await cleanup_demo_sessions(store, settings)

    assert await store.get_row("whatsapp_messages", temporary["id"]) is None
    assert await store.get_row("whatsapp_messages", normal["id"]) is not None
