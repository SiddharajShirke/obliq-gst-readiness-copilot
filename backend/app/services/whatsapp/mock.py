from __future__ import annotations

import uuid

from app.services.whatsapp.base import MessageSendResult


class MockWhatsAppProvider:
    """Transport-only mock. Persistence remains in the normal message service."""

    name = "mock"

    async def send_text(self, *, recipient: str, text: str) -> MessageSendResult:
        return MessageSendResult(
            external_message_id=f"mock-{uuid.uuid4()}",
            status="delivered",
            raw={"recipient": recipient, "text": text},
        )

    async def send_template(
        self,
        *,
        recipient: str,
        template_name: str,
        language_code: str,
        parameters: list[str],
    ) -> MessageSendResult:
        rendered = f"[{template_name}] " + " | ".join(parameters)
        return await self.send_text(recipient=recipient, text=rendered)

    async def download_media(self, media_id: str) -> tuple[bytes, str, str]:
        raise RuntimeError("Mock media is uploaded directly through the demo endpoint")
