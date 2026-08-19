from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.services.whatsapp.base import MessageSendResult, WhatsAppEvent


def normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(character for character in value if character.isdigit())
    return f"+{digits}" if digits else None


def parse_webhook_payload(payload: dict[str, Any]) -> list[WhatsAppEvent]:
    events: list[WhatsAppEvent] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []) or []:
                message_type = message.get("type")
                text = (message.get("text") or {}).get("body")
                media = message.get(message_type, {}) if message_type in {"document", "image", "video", "audio"} else {}
                events.append(
                    WhatsAppEvent(
                        kind="message",
                        external_message_id=message.get("id", ""),
                        sender_phone=normalize_phone(message.get("from")),
                        message_type=message_type,
                        text=text,
                        media_id=media.get("id"),
                        filename=media.get("filename"),
                        mime_type=media.get("mime_type"),
                        raw=message,
                    )
                )
            for status in value.get("statuses", []) or []:
                events.append(
                    WhatsAppEvent(
                        kind="status",
                        external_message_id=status.get("id", ""),
                        recipient_phone=normalize_phone(status.get("recipient_id")),
                        status=status.get("status"),
                        raw=status,
                    )
                )
    return events


@dataclass(slots=True)
class MetaCredentials:
    access_token: str
    phone_number_id: str
    waba_id: str = ""
    app_secret: str = ""
    webhook_verify_token: str = ""
    graph_api_version: str = "v26.0"
    test_recipient_number: str = ""
    document_request_template: str = "gst_document_request_v1"
    reminder_template: str = "gst_document_reminder_v1"

    @classmethod
    def from_file(cls, path: Path) -> "MetaCredentials":
        return cls(**json.loads(path.read_text(encoding="utf-8")))


class MetaWhatsAppProvider:
    name = "meta"

    def __init__(self, credentials: MetaCredentials) -> None:
        self.credentials = credentials
        self.base_url = f"https://graph.facebook.com/{credentials.graph_api_version}"

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.credentials.access_token}"}

    async def _send(self, payload: dict[str, Any]) -> MessageSendResult:
        url = f"{self.base_url}/{self.credentials.phone_number_id}/messages"
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            body = response.json()
        message_id = (body.get("messages") or [{}])[0].get("id", "")
        return MessageSendResult(external_message_id=message_id, status="sent", raw=body)

    async def send_text(self, *, recipient: str, text: str) -> MessageSendResult:
        return await self._send(
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": (normalize_phone(recipient) or recipient).removeprefix("+"),
                "type": "text",
                "text": {"preview_url": False, "body": text},
            }
        )

    async def send_template(
        self,
        *,
        recipient: str,
        template_name: str,
        language_code: str,
        parameters: list[str],
    ) -> MessageSendResult:
        components = []
        if parameters:
            components = [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": value} for value in parameters],
                }
            ]
        return await self._send(
            {
                "messaging_product": "whatsapp",
                "to": (normalize_phone(recipient) or recipient).removeprefix("+"),
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": language_code},
                    "components": components,
                },
            }
        )

    async def download_media(self, media_id: str) -> tuple[bytes, str, str]:
        async with httpx.AsyncClient(timeout=60) as client:
            metadata_response = await client.get(f"{self.base_url}/{media_id}", headers=self.headers)
            metadata_response.raise_for_status()
            metadata = metadata_response.json()
            media_response = await client.get(metadata["url"], headers=self.headers)
            media_response.raise_for_status()
        mime_type = metadata.get("mime_type") or media_response.headers.get("content-type", "application/octet-stream")
        extension = mime_type.split("/")[-1].replace("jpeg", "jpg")
        return media_response.content, mime_type, f"whatsapp-{media_id}.{extension}"
