from __future__ import annotations

import hashlib
import hmac
import logging
import re
import time
from typing import Any

import httpx
import jwt

from app.services.whatsapp.base import MessageSendResult, WhatsAppSendError
from app.services.whatsapp.security import normalize_whatsapp_phone

logger = logging.getLogger(__name__)
_PHONE_PATTERN = re.compile(r"(?<!\w)\+?\d{8,15}(?!\w)")
_WEBHOOK_MAX_AGE_SECONDS = 300


def _safe_error_message(message: object) -> str:
    if not isinstance(message, str) or not message.strip():
        return "Vonage rejected the outbound message"
    return _PHONE_PATTERN.sub("[redacted phone]", message).strip()[:500]


class VonageWhatsAppProvider:
    name = "vonage"

    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        signature_secret: str,
        whatsapp_from: str,
        messages_base_url: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        sender = normalize_whatsapp_phone(whatsapp_from)
        if not sender:
            raise ValueError("VONAGE_WHATSAPP_FROM must contain a valid phone number")
        self.api_key = api_key
        self.api_secret = api_secret
        self.signature_secret = signature_secret
        self.whatsapp_from = sender.removeprefix("+")
        self.messages_url = f"{messages_base_url.rstrip('/')}/v1/messages"
        self.client = client

    async def send_text(
        self,
        *,
        recipient: str,
        text: str,
        status_callback: str | None = None,
    ) -> MessageSendResult:
        normalized = normalize_whatsapp_phone(recipient)
        if not normalized:
            raise ValueError("Recipient must be a valid E.164 WhatsApp phone number")
        payload = {
            "channel": "whatsapp",
            "message_type": "text",
            "from": self.whatsapp_from,
            "to": normalized.removeprefix("+"),
            "text": text,
        }
        if status_callback:
            payload["webhook_url"] = status_callback

        try:
            if self.client is not None:
                response = await self.client.post(
                    self.messages_url,
                    json=payload,
                    auth=(self.api_key, self.api_secret),
                )
            else:
                async with httpx.AsyncClient(timeout=15) as client:
                    response = await client.post(
                        self.messages_url,
                        json=payload,
                        auth=(self.api_key, self.api_secret),
                    )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            error_payload: dict[str, Any] = {}
            try:
                parsed = exc.response.json()
                if isinstance(parsed, dict):
                    error_payload = parsed
            except ValueError:
                pass
            status = exc.response.status_code
            code_value = error_payload.get("title") or error_payload.get("code")
            code = str(code_value) if code_value is not None else None
            safe_message = _safe_error_message(
                error_payload.get("detail") or error_payload.get("message")
            )
            logger.error(
                "Vonage outbound send failed: status=%s code=%s message=%s",
                status,
                code,
                safe_message,
            )
            raise WhatsAppSendError(
                provider=self.name,
                status=status,
                code=code,
                safe_message=safe_message,
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Vonage WhatsApp message could not be sent") from exc

        data = response.json()
        message_uuid = data.get("message_uuid") if isinstance(data, dict) else None
        if not isinstance(message_uuid, str) or not message_uuid:
            raise RuntimeError("Vonage response did not include a message UUID")
        return MessageSendResult(
            provider=self.name,
            provider_message_id=message_uuid,
            initial_status="queued",
        )

    def validate_webhook(
        self,
        *,
        raw_body: bytes,
        authorization: str | None,
        now: int | None = None,
    ) -> bool:
        if not authorization or not authorization.startswith("Bearer "):
            return False
        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            return False
        try:
            claims = jwt.decode(
                token,
                self.signature_secret,
                algorithms=["HS256"],
                issuer="Vonage",
                options={
                    "verify_iat": False,
                    "require": ["iat", "jti", "iss", "api_key", "payload_hash"],
                },
            )
            issued_at = int(claims["iat"])
            current_time = int(time.time()) if now is None else now
            if issued_at > current_time + 60:
                return False
            if current_time - issued_at > _WEBHOOK_MAX_AGE_SECONDS:
                return False
            if not hmac.compare_digest(str(claims["api_key"]), self.api_key):
                return False
            expected_hash = hashlib.sha256(raw_body).hexdigest()
            return hmac.compare_digest(str(claims["payload_hash"]), expected_hash)
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            return False
