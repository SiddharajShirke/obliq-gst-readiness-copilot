from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.config import Settings
from app.repositories.memory import DEMO_ADMIN_ID, MemoryStore
from app.services.whatsapp.conversation import build_welcome_message, handle_text_command
from app.services.whatsapp.sessions import create_demo_session

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
async def test_welcome_and_status_messages_read_the_cloned_checklist() -> None:
    settings = _settings()
    store = MemoryStore(settings)
    created = await create_demo_session(store, settings, APP_ID, DEMO_ADMIN_ID)
    session = await store.get_row("whatsapp_demo_sessions", created.session_id)
    assert session is not None

    welcome = await build_welcome_message(store, session)
    status = await handle_text_command(store, session, "  status ")

    assert "Raj Traders" in welcome
    assert "April 2026" in welcome
    assert "Purchase Register" in welcome
    assert "/upload/" not in welcome
    assert "CA will send the secure upload link after review" in welcome
    assert status.action == "status"
    assert "Pending document categories" in status.text
    assert "GST Special Transactions" in status.text
    assert "GSTR-2B" not in status.text


@pytest.mark.asyncio
async def test_help_cancel_tax_and_unknown_messages_are_deterministic() -> None:
    settings = _settings()
    store = MemoryStore(settings)
    created = await create_demo_session(store, settings, APP_ID, DEMO_ADMIN_ID)
    session = await store.get_row("whatsapp_demo_sessions", created.session_id)
    assert session is not None

    help_reply = await handle_text_command(store, session, "HELP")
    cancel_reply = await handle_text_command(store, session, "cancel")
    tax_reply = await handle_text_command(store, session, "Can I claim ITC on this invoice?")
    unknown_reply = await handle_text_command(store, session, "Hello there")

    assert help_reply.action == "help"
    assert "STATUS" in help_reply.text
    assert cancel_reply.action == "cancel"
    assert tax_reply.action == "escalate"
    assert "CA review" in tax_reply.text
    assert unknown_reply.action == "unknown"
    assert "Reply STATUS" in unknown_reply.text
