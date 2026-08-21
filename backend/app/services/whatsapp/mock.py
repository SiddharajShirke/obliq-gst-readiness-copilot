from __future__ import annotations

import uuid

from app.services.whatsapp.base import MessageSendResult


class MockWhatsAppProvider:
    """Transport-only mock. Persistence remains in the normal message service."""

    name = "mock"

    async def send_text(
        self,
        *,
        recipient: str,
        text: str,
        status_callback: str | None = None,
    ) -> MessageSendResult:
        return MessageSendResult(
            provider=self.name,
            provider_message_id=f"mock-{uuid.uuid4()}",
            initial_status="delivered",
        )

    def validate_webhook(
        self,
        *,
        raw_body: bytes,
        authorization: str | None,
        now: int | None = None,
    ) -> bool:
        del raw_body, authorization, now
        return True
