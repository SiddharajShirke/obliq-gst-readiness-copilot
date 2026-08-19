from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class MessageSendResult:
    external_message_id: str
    status: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WhatsAppEvent:
    kind: str
    external_message_id: str
    sender_phone: str | None = None
    recipient_phone: str | None = None
    message_type: str | None = None
    text: str | None = None
    media_id: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    status: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class WhatsAppProvider(Protocol):
    name: str

    async def send_text(self, *, recipient: str, text: str) -> MessageSendResult: ...
    async def send_template(
        self,
        *,
        recipient: str,
        template_name: str,
        language_code: str,
        parameters: list[str],
    ) -> MessageSendResult: ...
    async def download_media(self, media_id: str) -> tuple[bytes, str, str]: ...
