from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class MessageSendResult:
    provider: str
    provider_message_id: str
    initial_status: str


class WhatsAppSendError(RuntimeError):
    def __init__(
        self,
        *,
        provider: str,
        status: int | None,
        code: str | None,
        safe_message: str,
    ) -> None:
        super().__init__(f"{provider} WhatsApp message could not be sent")
        self.provider = provider
        self.status = status
        self.code = code
        self.safe_message = safe_message


class WhatsAppProvider(Protocol):
    name: str

    async def send_text(
        self,
        *,
        recipient: str,
        text: str,
        status_callback: str | None = None,
    ) -> MessageSendResult: ...

    def validate_webhook(
        self,
        *,
        raw_body: bytes,
        authorization: str | None,
        now: int | None = None,
    ) -> bool: ...
