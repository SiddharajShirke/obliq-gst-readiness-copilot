from __future__ import annotations

import base64
import json
import logging

import httpx
import jwt
import pytest

from app.config import Settings
from app.services.whatsapp.base import WhatsAppSendError
from app.services.whatsapp.factory import get_whatsapp_provider
from app.services.whatsapp.vonage import VonageWhatsAppProvider


def _provider(
    handler,
    *,
    api_key: str = "api-key",
    api_secret: str = "api-secret",
    signature_secret: str = "signature-secret-with-enough-entropy",
) -> tuple[VonageWhatsAppProvider, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return (
        VonageWhatsAppProvider(
            api_key=api_key,
            api_secret=api_secret,
            signature_secret=signature_secret,
            whatsapp_from="whatsapp:+14155238886",
            messages_base_url="https://messages-sandbox.nexmo.com",
            client=client,
        ),
        client,
    )


@pytest.mark.asyncio
async def test_send_text_posts_sandbox_json_and_returns_message_uuid() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(202, json={"message_uuid": "aaaaaaaa-bbbb-4ccc-8ddd-0123456789ab"})

    provider, client = _provider(handler)
    try:
        result = await provider.send_text(
            recipient="whatsapp:whatsapp:+919876543210",
            text="Welcome to OBLIQ",
            status_callback="https://api.example.com/api/v1/webhooks/vonage/status",
        )
    finally:
        await client.aclose()

    assert captured["url"] == "https://messages-sandbox.nexmo.com/v1/messages"
    assert captured["authorization"] == (
        "Basic " + base64.b64encode(b"api-key:api-secret").decode()
    )
    assert captured["payload"] == {
        "channel": "whatsapp",
        "message_type": "text",
        "from": "14155238886",
        "to": "919876543210",
        "text": "Welcome to OBLIQ",
        "webhook_url": "https://api.example.com/api/v1/webhooks/vonage/status",
    }
    assert result.provider == "vonage"
    assert result.provider_message_id == "aaaaaaaa-bbbb-4ccc-8ddd-0123456789ab"
    assert result.initial_status == "queued"


@pytest.mark.asyncio
async def test_send_text_preserves_safe_vonage_error_fields(caplog) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            429,
            json={
                "title": "1000",
                "detail": "Throttled for recipient +919876543210",
            },
        )

    provider, client = _provider(handler, api_secret="do-not-log-this-secret")
    try:
        with caplog.at_level(logging.ERROR), pytest.raises(WhatsAppSendError) as caught:
            await provider.send_text(
                recipient="+919876543210",
                text="STATUS",
                status_callback=None,
            )
    finally:
        await client.aclose()

    assert caught.value.status == 429
    assert caught.value.code == "1000"
    assert caught.value.safe_message == "Throttled for recipient [redacted phone]"
    assert "status=429 code=1000" in caplog.text
    assert "do-not-log-this-secret" not in caplog.text
    assert "+919876543210" not in caplog.text


def test_validate_webhook_verifies_signature_claims_timestamp_and_payload_hash() -> None:
    raw_body = b'{"message_uuid":"aaaaaaaa-bbbb-4ccc-8ddd-0123456789ab","text":"STATUS"}'
    now = 1_700_000_000
    payload_hash = __import__("hashlib").sha256(raw_body).hexdigest()
    token = jwt.encode(
        {
            "iat": now,
            "jti": "event-id",
            "iss": "Vonage",
            "api_key": "api-key",
            "payload_hash": payload_hash,
        },
        "signature-secret-with-enough-entropy",
        algorithm="HS256",
    )
    provider, client = _provider(lambda request: httpx.Response(500))

    try:
        assert provider.validate_webhook(
            raw_body=raw_body,
            authorization=f"Bearer {token}",
            now=now,
        )
        assert not provider.validate_webhook(
            raw_body=raw_body + b" ",
            authorization=f"Bearer {token}",
            now=now,
        )
        assert not provider.validate_webhook(
            raw_body=raw_body,
            authorization=f"Bearer {token}",
            now=now + 301,
        )
    finally:
        import asyncio

        asyncio.run(client.aclose())


def test_factory_allows_mock_only_in_tests_and_rejects_unsupported_provider() -> None:
    mock_settings = Settings(app_env="test", whatsapp_provider="mock", _env_file=None)
    assert get_whatsapp_provider(mock_settings).name == "mock"

    with pytest.raises(RuntimeError, match="Unsupported WhatsApp provider"):
        get_whatsapp_provider(mock_settings.model_copy(update={"whatsapp_provider": "unsupported"}))

    with pytest.raises(RuntimeError, match="only available in tests"):
        get_whatsapp_provider(mock_settings.model_copy(update={"app_env": "development"}))
