from __future__ import annotations

import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.repositories import get_store
from app.repositories.memory import MemoryStore
from app.services.whatsapp.base import MessageSendResult, WhatsAppSendError

AUTH = {"Authorization": "Bearer demo-admin-token"}
APP_ID = "30000000-0000-0000-0000-000000000001"


class FakeVonageProvider:
    name = "vonage"

    def __init__(self) -> None:
        self.sent: list[dict[str, str | None]] = []
        self.failure: WhatsAppSendError | None = None

    async def send_text(
        self,
        *,
        recipient: str,
        text: str,
        status_callback: str | None = None,
    ) -> MessageSendResult:
        if self.failure:
            raise self.failure
        self.sent.append(
            {"recipient": recipient, "text": text, "status_callback": status_callback}
        )
        return MessageSendResult(
            provider="vonage",
            provider_message_id=f"00000000-0000-4000-8000-{len(self.sent):012d}",
            initial_status="queued",
        )

    def validate_webhook(self, *, raw_body, authorization, now=None) -> bool:
        del raw_body, now
        return authorization == "Bearer valid"


@pytest.fixture
def vonage_client(monkeypatch, tmp_path):
    settings = Settings(
        app_env="test",
        whatsapp_provider="mock",
        upload_token_pepper="upload-pepper",
        local_upload_dir=tmp_path / "uploads",
        whatsapp_demo_token_pepper="token-pepper",
        whatsapp_phone_hash_pepper="phone-pepper",
        whatsapp_phone_encryption_key=Fernet.generate_key().decode(),
        vonage_whatsapp_from="14155238886",
        vonage_sandbox_join_message="join obliq-demo",
        public_base_url="https://api.example.com",
        _env_file=None,
    )
    store = MemoryStore(settings)
    provider = FakeVonageProvider()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    monkeypatch.setattr(
        "app.api.v1.whatsapp.get_whatsapp_provider", lambda configured: provider
    )
    with TestClient(app) as test_client:
        yield test_client, store, provider
    app.dependency_overrides.clear()


def _create_session(client: TestClient) -> dict:
    response = client.post(
        f"/api/v1/applications/{APP_ID}/whatsapp-demo-sessions", headers=AUTH
    )
    assert response.status_code == 201, response.text
    return response.json()


def _inbound(
    client: TestClient,
    message_uuid: str,
    body: str,
    *,
    message_type: str = "text",
    signature: str = "valid",
):
    payload: dict[str, object] = {
        "channel": "whatsapp",
        "message_uuid": message_uuid,
        "from": "919876543210",
        "to": "14155238886",
        "timestamp": "2026-08-20T12:00:00Z",
        "message_type": message_type,
    }
    if message_type == "text":
        payload["text"] = body
    else:
        payload[message_type] = {
            "url": "https://api-eu.nexmo.com/v3/media/private-id",
            "name": "private-document.pdf",
        }
    return client.post(
        "/api/v1/webhooks/vonage/whatsapp",
        headers={"Authorization": f"Bearer {signature}"},
        content=json.dumps(payload, separators=(",", ":")),
    )


def test_session_api_requires_dashboard_token_and_hides_full_phone(vonage_client) -> None:
    client, store, _ = vonage_client
    created = _create_session(client)

    denied = client.get(
        f"/api/v1/whatsapp-demo-sessions/{created['session_id']}", headers=AUTH
    )
    allowed = client.get(
        f"/api/v1/whatsapp-demo-sessions/{created['session_id']}",
        headers={**AUTH, "X-OBLIQ-Demo-Access-Token": created["dashboard_access_token"]},
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "waiting_for_start"
    diagnostic = allowed.json()["connection_diagnostic"]
    assert diagnostic.pop("waited_seconds") >= 0
    assert diagnostic == {
        "state": "awaiting_valid_start",
        "valid_start_received": False,
        "session_created_at": diagnostic["session_created_at"],
        "connected_at": None,
        "inbound_webhook_url": (
            "https://api.example.com/api/v1/webhooks/vonage/whatsapp"
        ),
        "status_callback_url": (
            "https://api.example.com/api/v1/webhooks/vonage/status"
        ),
    }
    assert allowed.json()["upload_workflow"] == {
        "state": "waiting_for_connection",
        "secure_link_created": False,
        "received_document_count": 0,
        "latest_link_expires_at": None,
    }
    assert "9876543210" not in allowed.text
    session = asyncio.run(store.get_row("whatsapp_demo_sessions", created["session_id"]))
    normal_applications = client.get("/api/v1/applications", headers=AUTH)
    assert normal_applications.status_code == 200
    assert session["session_application_id"] not in {
        row["id"] for row in normal_applications.json()
    }


def test_invalid_signature_changes_nothing_and_valid_start_is_idempotent(
    vonage_client,
) -> None:
    client, store, provider = vonage_client
    created = _create_session(client)
    before = len(asyncio.run(store.list_rows("whatsapp_messages")))

    rejected = _inbound(
        client,
        "10000000-0000-4000-8000-000000000001",
        created["start_message"],
        signature="invalid",
    )
    assert rejected.status_code == 403
    assert len(asyncio.run(store.list_rows("whatsapp_messages"))) == before

    message_uuid = "10000000-0000-4000-8000-000000000002"
    first = _inbound(client, message_uuid, created["start_message"])
    duplicate = _inbound(client, message_uuid, created["start_message"])

    assert first.status_code == duplicate.status_code == 200
    assert first.content == b""
    inbound = asyncio.run(
        store.list_rows("whatsapp_messages", {"provider_message_id": message_uuid})
    )
    assert len(inbound) == 1
    assert len(provider.sent) == 1
    session = asyncio.run(store.get_row("whatsapp_demo_sessions", created["session_id"]))
    assert session["status"] == "active"
    assert session["judge_phone_encrypted"] != "+919876543210"
    links = asyncio.run(
        store.list_rows("upload_links", {"demo_session_id": created["session_id"]})
    )
    assert links == []
    assert "/upload/" not in str(provider.sent[0]["text"])
    assert "CA will send the secure upload link after review" in str(
        provider.sent[0]["text"]
    )
    outbound = asyncio.run(
        store.list_rows(
            "whatsapp_messages",
            {"demo_session_id": created["session_id"], "direction": "outbound"},
        )
    )
    assert len(outbound) == 1
    assert "/upload/" not in outbound[0]["content"]
    assert str(provider.sent[0]["text"]) == outbound[0]["content"]


def test_signed_start_reaches_session_scoped_secure_upload_submission(
    vonage_client,
) -> None:
    client, store, _ = vonage_client
    pending = client.post(
        f"/api/v1/applications/{APP_ID}/document-request/draft", headers=AUTH
    )
    assert pending.status_code == 201, pending.text
    reminder_id = pending.json()["id"]
    created = _create_session(client)
    session_id = created["session_id"]
    access_headers = {
        **AUTH,
        "X-OBLIQ-Demo-Session-Id": session_id,
        "X-OBLIQ-Demo-Access-Token": created["dashboard_access_token"],
    }

    started = _inbound(
        client,
        "10000000-0000-4000-8000-000000000099",
        created["start_message"],
    )
    assert started.status_code == 200, started.text
    status_response = client.get(
        f"/api/v1/whatsapp-demo-sessions/{session_id}", headers=access_headers
    )
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["connection_diagnostic"]["state"] == "connected"
    assert status_response.json()["connection_diagnostic"]["valid_start_received"] is True
    assert status_response.json()["upload_workflow"]["state"] == "ready_to_prepare_request"

    prepared = client.post(
        f"/api/v1/reminders/{reminder_id}/prepare", headers=access_headers
    )
    assert prepared.status_code == 200, prepared.text
    retried_prepare = client.post(
        f"/api/v1/reminders/{reminder_id}/prepare", headers=access_headers
    )
    assert retried_prepare.status_code == 200, retried_prepare.text
    links_after_retry = asyncio.run(
        store.list_rows("upload_links", {"demo_session_id": session_id})
    )
    assert len([row for row in links_after_retry if not row.get("revoked_at")]) == 1
    stale_token = Path(urlparse(prepared.json()["upload_url"]).path).name
    assert client.get(f"/api/v1/public/upload/{stale_token}").status_code == 410
    upload_url = retried_prepare.json()["upload_url"]
    token = Path(urlparse(upload_url).path).name
    public_context = client.get(f"/api/v1/public/upload/{token}")
    assert public_context.status_code == 200, public_context.text
    requirement = next(
        row
        for row in public_context.json()["checklist"]
        if row["requirement_type"] == "sales_register"
    )

    uploaded = client.post(
        f"/api/v1/public/upload/{token}",
        data={"requirement_id": requirement["id"]},
        files={
            "file": (
                "Sales_Register_April.csv",
                b"invoice_number,invoice_date,taxable_value\nS-1,2026-04-02,1000\n",
                "text/csv",
            )
        },
    )
    assert uploaded.status_code == 201, uploaded.text
    submitted = client.post(f"/api/v1/public/upload/{token}/submit")
    assert submitted.status_code == 202, submitted.text

    session = asyncio.run(store.get_row("whatsapp_demo_sessions", session_id))
    assert session is not None
    clone_id = session["session_application_id"]
    document = asyncio.run(store.get_row("documents", uploaded.json()["id"]))
    assert document is not None
    assert document["application_id"] == clone_id
    assert document["application_id"] != APP_ID
    batches = asyncio.run(
        store.list_rows("document_submission_batches", {"application_id": clone_id})
    )
    assert len(batches) == 1
    assert batches[0]["demo_session_id"] == session_id

    final_status = client.get(
        f"/api/v1/whatsapp-demo-sessions/{session_id}", headers=access_headers
    )
    assert final_status.status_code == 200, final_status.text
    assert final_status.json()["upload_workflow"]["state"] == "documents_received"
    assert final_status.json()["upload_workflow"]["secure_link_created"] is True
    assert final_status.json()["upload_workflow"]["received_document_count"] == 1


def test_invalid_start_rate_limit_suppresses_outbound_reply(
    vonage_client, monkeypatch
) -> None:
    client, _, provider = vonage_client

    def allow(key: str, *, limit: int, window_seconds: int) -> bool:
        del limit, window_seconds
        return not key.startswith("invalid-start:")

    monkeypatch.setattr("app.api.v1.whatsapp.rate_limiter.allow", allow)
    response = _inbound(
        client,
        "10000000-0000-4000-8000-000000000003",
        "START OBLIQ DEMO A7K2P9DX",
    )

    assert response.status_code == 200
    assert provider.sent == []


def test_sandbox_join_message_is_ignored_before_session_binding(vonage_client) -> None:
    client, store, provider = vonage_client
    messages_before = len(asyncio.run(store.list_rows("whatsapp_messages")))

    response = _inbound(
        client,
        "10000000-0000-4000-8000-000000000020",
        "  JOIN OBLIQ-DEMO  ",
    )

    assert response.status_code == 200
    assert len(asyncio.run(store.list_rows("whatsapp_messages"))) == messages_before
    assert provider.sent == []


def test_sandbox_join_message_is_ignored_after_session_binding(vonage_client) -> None:
    client, store, provider = vonage_client
    created = _create_session(client)
    start = _inbound(
        client,
        "10000000-0000-4000-8000-000000000021",
        created["start_message"],
    )
    assert start.status_code == 200
    messages_before = len(asyncio.run(store.list_rows("whatsapp_messages")))
    sends_before = len(provider.sent)

    response = _inbound(
        client,
        "10000000-0000-4000-8000-000000000022",
        "JOIN OBLIQ-DEMO",
    )

    assert response.status_code == 200
    assert len(asyncio.run(store.list_rows("whatsapp_messages"))) == messages_before
    assert len(provider.sent) == sends_before


def test_vonage_failure_persists_safe_error_fields_on_one_outbound_row(
    vonage_client,
) -> None:
    client, store, provider = vonage_client
    provider.failure = WhatsAppSendError(
        provider="vonage",
        status=429,
        code="1000",
        safe_message="Throttled",
    )
    created = _create_session(client)

    response = _inbound(
        client,
        "10000000-0000-4000-8000-000000000004",
        created["start_message"],
    )

    assert response.status_code == 200
    rows = asyncio.run(
        store.list_rows(
            "whatsapp_messages",
            {"demo_session_id": created["session_id"], "direction": "outbound"},
        )
    )
    assert len(rows) == 1
    assert rows[0]["provider_message_id"] is None
    assert rows[0]["delivery_status"] == "failed"
    assert rows[0]["error_code"] == "1000"
    assert rows[0]["error_message"] == "Throttled"
    assert rows[0]["failed_at"]


def test_commands_media_boundary_escalation_and_status_callback(vonage_client) -> None:
    client, store, provider = vonage_client
    created = _create_session(client)
    assert _inbound(
        client,
        "10000000-0000-4000-8000-000000000010",
        created["start_message"],
    ).status_code == 200
    documents_before = len(asyncio.run(store.list_rows("documents")))

    assert _inbound(client, "10000000-0000-4000-8000-000000000011", "STATUS").status_code == 200
    assert "Purchase Register" in provider.sent[-1]["text"]
    assert _inbound(client, "10000000-0000-4000-8000-000000000012", "HELP").status_code == 200
    assert "Available commands" in provider.sent[-1]["text"]
    tax_question = _inbound(
        client,
        "10000000-0000-4000-8000-000000000013",
        "Can I claim ITC?",
    )
    assert tax_question.status_code == 200
    assert "CA review" in provider.sent[-1]["text"]
    escalations = asyncio.run(
        store.list_rows("audit_events", {"action": "whatsapp.tax_question_escalated"})
    )
    assert len(escalations) == 1
    assert _inbound(
        client,
        "10000000-0000-4000-8000-000000000014",
        "",
        message_type="image",
    ).status_code == 200
    assert "secure upload link" in provider.sent[-1]["text"].lower()
    assert "not downloaded" in provider.sent[-1]["text"].lower()
    assert len(asyncio.run(store.list_rows("documents"))) == documents_before

    outbound_uuid = "00000000-0000-4000-8000-000000000001"
    callback_payload = {
        "message_uuid": outbound_uuid,
        "channel": "whatsapp",
        "status": "delivered",
        "timestamp": "2026-08-20T12:00:01Z",
    }
    callback = client.post(
        "/api/v1/webhooks/vonage/status",
        headers={"Authorization": "Bearer valid"},
        json=callback_payload,
    )
    duplicate = client.post(
        "/api/v1/webhooks/vonage/status",
        headers={"Authorization": "Bearer valid"},
        json=callback_payload,
    )
    assert callback.status_code == duplicate.status_code == 200
    rows = asyncio.run(
        store.list_rows("whatsapp_messages", {"provider_message_id": outbound_uuid})
    )
    assert len(rows) == 1
    assert rows[0]["delivery_status"] == "delivered"
    assert rows[0]["delivered_at"]

    failed = client.post(
        "/api/v1/webhooks/vonage/status",
        headers={"Authorization": "Bearer valid"},
        json={
            **callback_payload,
            "status": "rejected",
            "error": {"title": "1022", "detail": "Message rejected"},
        },
    )
    assert failed.status_code == 200
    failed_row = asyncio.run(
        store.list_rows("whatsapp_messages", {"provider_message_id": outbound_uuid})
    )[0]
    assert failed_row["delivery_status"] == "failed"
    assert failed_row["error_code"] == "1022"
    assert failed_row["failed_at"]

    before_invalid = failed_row.copy()
    invalid_callback = client.post(
        "/api/v1/webhooks/vonage/status",
        headers={"Authorization": "Bearer invalid"},
        json={**callback_payload, "status": "read"},
    )
    assert invalid_callback.status_code == 403
    after_invalid = asyncio.run(
        store.list_rows("whatsapp_messages", {"provider_message_id": outbound_uuid})
    )[0]
    assert after_invalid == before_invalid

    assert _inbound(client, "10000000-0000-4000-8000-000000000015", "CANCEL").status_code == 200
    session = asyncio.run(store.get_row("whatsapp_demo_sessions", created["session_id"]))
    assert session["status"] == "cancelled"
