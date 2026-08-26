from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.repositories import get_store
from app.repositories.memory import MemoryStore
from app.services.whatsapp.base import MessageSendResult
from app.services.whatsapp.security import PhoneProtector

AUTH = {"Authorization": "Bearer demo-admin-token"}
APP_ID = "30000000-0000-0000-0000-000000000001"


class RecordingProvider:
    name = "vonage"

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_text(self, *, recipient, text, status_callback=None):
        self.sent.append(
            {"recipient": recipient, "text": text, "status_callback": status_callback}
        )
        return MessageSendResult(
            provider="vonage",
            provider_message_id="00000000-0000-4000-8000-000000000777",
            initial_status="queued",
        )

    def validate_webhook(self, *, raw_body, authorization, now=None):
        return True


@pytest.fixture
def connectivity_client(tmp_path, monkeypatch):
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
        public_base_url="https://api.example.test",
        frontend_url="https://dashboard.example.test",
        _env_file=None,
    )
    store = MemoryStore(settings)
    provider = RecordingProvider()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    monkeypatch.setattr(
        "app.api.v1.whatsapp.get_whatsapp_provider", lambda configured: provider
    )
    with TestClient(app) as test_client:
        yield test_client, store, settings, provider
    app.dependency_overrides.clear()


def test_collection_status_is_dynamic_and_never_ready_for_filing(
    connectivity_client,
) -> None:
    client, store, _, _ = connectivity_client
    requirements = asyncio.run(
        store.list_rows("document_requirements", {"application_id": APP_ID}, order="label")
    )
    asyncio.run(
        store.update_row("document_requirements", requirements[0]["id"], {"status": "received"})
    )
    asyncio.run(
        store.update_row("document_requirements", requirements[1]["id"], {"status": "received"})
    )

    response = client.get(
        f"/api/v1/applications/{APP_ID}/document-collection-status",
        headers=AUTH,
    )

    assert response.status_code == 200, response.text
    assert response.json()["required_count"] == len(requirements)
    assert response.json()["received_count"] == 2
    assert response.json()["missing_count"] == len(requirements) - 2
    assert response.json()["progress_percent"] == round(200 / len(requirements))
    assert response.json()["workflow_status"] == "partially_received"
    assert response.json()["workflow_status"] != "ready_for_filing"


def test_phase2_routes_cannot_mark_application_ready_for_filing(
    connectivity_client,
) -> None:
    client, _, _, _ = connectivity_client

    approval = client.post(f"/api/v1/applications/{APP_ID}/approve", headers=AUTH)
    direct_update = client.patch(
        f"/api/v1/applications/{APP_ID}",
        headers=AUTH,
        json={"status": "ready_for_filing"},
    )

    assert approval.status_code == 409
    assert direct_update.status_code == 422


def test_draft_request_without_session_is_preserved_for_connection(
    connectivity_client,
) -> None:
    client, store, _, _ = connectivity_client

    response = client.post(
        f"/api/v1/applications/{APP_ID}/document-request/draft",
        headers=AUTH,
    )

    assert response.status_code == 201, response.text
    assert response.json()["requires_connection"] is True
    assert response.json()["demo_session_id"] is None
    assert response.json()["upload_url"] is None
    assert asyncio.run(store.list_rows("upload_links")) == []
    assert "Sales Register" in response.json()["draft_message"]


def test_reminder_at_complete_collection_does_not_create_a_draft(
    connectivity_client,
) -> None:
    client, store, _, _ = connectivity_client
    requirements = asyncio.run(
        store.list_rows("document_requirements", {"application_id": APP_ID})
    )
    for requirement in requirements:
        asyncio.run(
            store.update_row("document_requirements", requirement["id"], {"status": "received"})
        )

    response = client.post(
        f"/api/v1/applications/{APP_ID}/reminders/draft",
        headers=AUTH,
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "reminder_needed": False,
        "message": "All required document categories have been received. No reminder is needed.",
    }
    assert asyncio.run(store.list_rows("reminders")) == []


def test_reconnect_reuses_retained_clone_and_clears_phone_binding(
    connectivity_client,
) -> None:
    client, store, _, _ = connectivity_client
    created = client.post(
        f"/api/v1/applications/{APP_ID}/whatsapp-demo-sessions", headers=AUTH
    ).json()
    session = asyncio.run(store.get_row("whatsapp_demo_sessions", created["session_id"]))
    assert session is not None
    clone_id = session["session_application_id"]
    requirement = asyncio.run(
        store.list_rows(
            "document_requirements", {"application_id": clone_id}, limit=1
        )
    )[0]
    asyncio.run(
        store.update_row("document_requirements", requirement["id"], {"status": "received"})
    )
    asyncio.run(
        store.update_row(
            "whatsapp_demo_sessions",
            session["id"],
            {
                "status": "cancelled",
                "judge_phone_hash": "old-hash",
                "judge_phone_encrypted": "old-ciphertext",
                "judge_phone_last_four": "3210",
                "provider_user_id_hash": "old-provider-user",
                "cancelled_at": datetime.now(UTC).isoformat(),
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        )
    )

    response = client.post(
        f"/api/v1/whatsapp-demo-sessions/{session['id']}/reconnect",
        headers={
            **AUTH,
            "X-OBLIQ-Demo-Access-Token": created["dashboard_access_token"],
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["session_id"] == session["id"]
    reconnected = asyncio.run(store.get_row("whatsapp_demo_sessions", session["id"]))
    assert reconnected is not None
    assert reconnected["session_application_id"] == clone_id
    assert reconnected["status"] == "waiting_for_start"
    assert reconnected["judge_phone_hash"] is None
    assert reconnected["judge_phone_encrypted"] is None
    assert reconnected["judge_phone_last_four"] is None
    assert reconnected["provider_user_id_hash"] is None
    retained = asyncio.run(store.get_row("document_requirements", requirement["id"]))
    assert retained is not None and retained["status"] == "received"


def test_pending_request_is_prepared_after_connection_without_redrafting(
    connectivity_client,
) -> None:
    client, store, settings, _ = connectivity_client
    pending = client.post(
        f"/api/v1/applications/{APP_ID}/document-request/draft", headers=AUTH
    )
    assert pending.status_code == 201
    reminder_id = pending.json()["id"]
    created = client.post(
        f"/api/v1/applications/{APP_ID}/whatsapp-demo-sessions", headers=AUTH
    ).json()
    session = asyncio.run(store.get_row("whatsapp_demo_sessions", created["session_id"]))
    assert session is not None
    protected = PhoneProtector(
        hash_pepper=settings.whatsapp_phone_hash_pepper,
        encryption_key=settings.whatsapp_phone_encryption_key,
    ).protect("+919999998888")
    asyncio.run(
        store.update_row(
            "whatsapp_demo_sessions",
            session["id"],
            {
                "status": "active",
                "judge_phone_hash": protected.lookup_hash,
                "judge_phone_encrypted": protected.encrypted,
            },
        )
    )

    prepared = client.post(
        f"/api/v1/reminders/{reminder_id}/prepare",
        headers={
            **AUTH,
            "X-OBLIQ-Demo-Session-Id": session["id"],
            "X-OBLIQ-Demo-Access-Token": created["dashboard_access_token"],
        },
    )

    assert prepared.status_code == 200, prepared.text
    assert prepared.json()["id"] == reminder_id
    assert prepared.json()["requires_connection"] is False
    assert prepared.json()["application_id"] == session["session_application_id"]
    assert "/upload/" in prepared.json()["draft_message"]
    assert len(asyncio.run(store.list_rows("reminders"))) == 1


def test_active_session_draft_creates_clone_bound_upload_link_and_send_reuses_phone(
    connectivity_client,
) -> None:
    client, store, settings, provider = connectivity_client
    created = client.post(
        f"/api/v1/applications/{APP_ID}/whatsapp-demo-sessions", headers=AUTH
    ).json()
    session = asyncio.run(store.get_row("whatsapp_demo_sessions", created["session_id"]))
    assert session is not None
    protected = PhoneProtector(
        hash_pepper=settings.whatsapp_phone_hash_pepper,
        encryption_key=settings.whatsapp_phone_encryption_key,
    ).protect("+919999998888")
    asyncio.run(
        store.update_row(
            "whatsapp_demo_sessions",
            session["id"],
            {
                "status": "active",
                "judge_phone_hash": protected.lookup_hash,
                "judge_phone_encrypted": protected.encrypted,
                "judge_phone_last_four": protected.last_four,
                "connected_at": datetime.now(UTC).isoformat(),
            },
        )
    )
    headers = {
        **AUTH,
        "X-OBLIQ-Demo-Session-Id": session["id"],
        "X-OBLIQ-Demo-Access-Token": created["dashboard_access_token"],
    }

    drafted = client.post(
        f"/api/v1/applications/{APP_ID}/document-request/draft", headers=headers
    )

    assert drafted.status_code == 201, drafted.text
    payload = drafted.json()
    assert payload["requires_connection"] is False
    assert payload["demo_session_id"] == session["id"]
    assert payload["application_id"] == session["session_application_id"]
    assert payload["upload_url"].startswith("https://dashboard.example.test/upload/")
    links = asyncio.run(store.list_rows("upload_links"))
    assert links[-1]["application_id"] == session["session_application_id"]
    assert links[-1]["demo_session_id"] == session["id"]

    sent = client.post(
        f"/api/v1/applications/{APP_ID}/document-request/approve-send",
        headers=headers,
        json={"reminder_id": payload["id"], "message": payload["draft_message"]},
    )

    assert sent.status_code == 200, sent.text
    assert provider.sent[-1]["recipient"] == "+919999998888"
    outbound = asyncio.run(
        store.list_rows(
            "whatsapp_messages",
            {"demo_session_id": session["id"], "direction": "outbound"},
        )
    )[-1]
    assert outbound["application_id"] == session["session_application_id"]
    reminder = asyncio.run(store.get_row("reminders", payload["id"]))
    assert reminder is not None
    assert reminder["provider_message_id"] == outbound["provider_message_id"]
    audit = client.get(f"/api/v1/applications/{APP_ID}/audit", headers=headers)
    assert audit.status_code == 200, audit.text
    assert {event["action"] for event in audit.json()} >= {
        "document_request_drafted",
        "document_request_sent",
    }


@pytest.mark.parametrize(
    "tamper", ["origin", "token", "binding", "revoked", "expired"]
)
def test_document_request_rejects_cross_environment_or_unbound_upload_link(
    connectivity_client,
    tamper: str,
) -> None:
    client, store, settings, provider = connectivity_client
    created = client.post(
        f"/api/v1/applications/{APP_ID}/whatsapp-demo-sessions", headers=AUTH
    ).json()
    session = asyncio.run(store.get_row("whatsapp_demo_sessions", created["session_id"]))
    assert session is not None
    protected = PhoneProtector(
        hash_pepper=settings.whatsapp_phone_hash_pepper,
        encryption_key=settings.whatsapp_phone_encryption_key,
    ).protect("+919999998888")
    asyncio.run(
        store.update_row(
            "whatsapp_demo_sessions",
            session["id"],
            {
                "status": "active",
                "judge_phone_hash": protected.lookup_hash,
                "judge_phone_encrypted": protected.encrypted,
                "judge_phone_last_four": protected.last_four,
                "connected_at": datetime.now(UTC).isoformat(),
            },
        )
    )
    headers = {
        **AUTH,
        "X-OBLIQ-Demo-Session-Id": session["id"],
        "X-OBLIQ-Demo-Access-Token": created["dashboard_access_token"],
    }
    drafted = client.post(
        f"/api/v1/applications/{APP_ID}/document-request/draft", headers=headers
    ).json()
    message = drafted["draft_message"]
    if tamper == "origin":
        message = message.replace(
            "https://dashboard.example.test", "http://localhost:3000"
        )
    elif tamper == "token":
        original_token = drafted["upload_url"].rsplit("/", 1)[-1]
        replacement = "A" * len(original_token)
        message = message.replace(original_token, replacement)
    elif tamper == "binding":
        asyncio.run(
            store.update_row(
                "upload_links",
                drafted["upload_link_id"],
                {"application_id": APP_ID},
            )
        )
    elif tamper == "revoked":
        asyncio.run(
            store.update_row(
                "upload_links",
                drafted["upload_link_id"],
                {"revoked_at": datetime.now(UTC).isoformat()},
            )
        )
    else:
        asyncio.run(
            store.update_row(
                "upload_links",
                drafted["upload_link_id"],
                {"expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()},
            )
        )

    sent = client.post(
        f"/api/v1/applications/{APP_ID}/document-request/approve-send",
        headers=headers,
        json={"reminder_id": drafted["id"], "message": message},
    )

    assert sent.status_code == 409, sent.text
    assert "Prepare a new request" in sent.json()["detail"]
    assert provider.sent == []


def test_connected_request_upload_submission_extraction_and_overview_are_end_to_end(
    connectivity_client,
) -> None:
    client, store, settings, provider = connectivity_client
    created = client.post(
        f"/api/v1/applications/{APP_ID}/whatsapp-demo-sessions", headers=AUTH
    ).json()
    session = asyncio.run(store.get_row("whatsapp_demo_sessions", created["session_id"]))
    assert session is not None
    protected = PhoneProtector(
        hash_pepper=settings.whatsapp_phone_hash_pepper,
        encryption_key=settings.whatsapp_phone_encryption_key,
    ).protect("+919999998888")
    asyncio.run(
        store.update_row(
            "whatsapp_demo_sessions",
            session["id"],
            {
                "status": "active",
                "judge_phone_hash": protected.lookup_hash,
                "judge_phone_encrypted": protected.encrypted,
                "judge_phone_last_four": protected.last_four,
                "connected_at": datetime.now(UTC).isoformat(),
            },
        )
    )
    headers = {
        **AUTH,
        "X-OBLIQ-Demo-Session-Id": session["id"],
        "X-OBLIQ-Demo-Access-Token": created["dashboard_access_token"],
    }
    drafted = client.post(
        f"/api/v1/applications/{APP_ID}/document-request/draft", headers=headers
    ).json()
    sent = client.post(
        f"/api/v1/applications/{APP_ID}/document-request/approve-send",
        headers=headers,
        json={"reminder_id": drafted["id"], "message": drafted["draft_message"]},
    )
    assert sent.status_code == 200, sent.text
    assert len(provider.sent) == 1

    raw_token = drafted["upload_url"].rsplit("/", 1)[-1]
    public_context = client.get(f"/api/v1/public/upload/{raw_token}")
    assert public_context.status_code == 200, public_context.text
    checklist = public_context.json()["checklist"]
    assert len(checklist) == 6
    for index, requirement in enumerate(checklist, start=1):
        content = (
            "Invoice No,Invoice Date,Taxable Value,CGST,SGST,Invoice Total\n"
            f"E2E-{index},2026-04-{index + 1:02d},1000,90,90,1180\n"
        ).encode()
        uploaded = client.post(
            f"/api/v1/public/upload/{raw_token}",
            data={"requirement_id": requirement["id"]},
            files={
                "file": (
                    f"{index:02d}_{requirement['label'].replace(' ', '_')}.csv",
                    content,
                    "text/csv",
                )
            },
        )
        assert uploaded.status_code == 201, uploaded.text
        assert uploaded.json()["processing_status"] == "awaiting_submission"

    submitted = client.post(f"/api/v1/public/upload/{raw_token}/submit")
    assert submitted.status_code == 202, submitted.text
    batch_status = client.get(f"/api/v1/public/upload/{raw_token}/status")
    assert batch_status.status_code == 200, batch_status.text
    batch = batch_status.json()["latest_submission_batch"]
    assert batch["status"] == "completed"
    assert batch["document_count"] == 6
    assert batch["completed_count"] == 6
    assert batch["failed_count"] == 0

    application_id = session["session_application_id"]
    documents = asyncio.run(
        store.list_rows("documents", {"application_id": application_id})
    )
    extractions = asyncio.run(store.list_rows("document_extractions"))
    records = asyncio.run(
        store.list_rows("invoice_records", {"application_id": application_id})
    )
    assert len(documents) == 6
    assert all(
        document["processing_status"] in {"ready_for_review", "needs_review"}
        for document in documents
    )
    document_ids = {document["id"] for document in documents}
    assert len(
        [row for row in extractions if row["document_id"] in document_ids]
    ) == 6
    assert len(records) == 6

    overview = client.get(
        f"/api/v1/applications/{APP_ID}/document-collection-status",
        headers=headers,
    )
    assert overview.status_code == 200, overview.text
    payload = overview.json()
    assert payload["effective_application_id"] == application_id
    assert payload["received_count"] == 6
    assert payload["progress_percent"] == 100
    assert payload["workflow"]["current_stage"] == "extraction_review"
    assert payload["workflow"]["extraction"]["record_count"] == 6
    assert payload["workflow"]["extraction"]["pending_count"] == 6
    actions = {row["action"] for row in asyncio.run(store.list_rows("audit_events"))}
    assert {
        "document_request_sent",
        "upload_completed",
        "checklist_requirement_received",
    } <= actions


def test_reminder_uses_only_live_missing_rows_and_reuses_existing_link(
    connectivity_client,
) -> None:
    client, store, settings, _ = connectivity_client
    created = client.post(
        f"/api/v1/applications/{APP_ID}/whatsapp-demo-sessions", headers=AUTH
    ).json()
    session = asyncio.run(store.get_row("whatsapp_demo_sessions", created["session_id"]))
    assert session is not None
    protected = PhoneProtector(
        hash_pepper=settings.whatsapp_phone_hash_pepper,
        encryption_key=settings.whatsapp_phone_encryption_key,
    ).protect("+919999998888")
    asyncio.run(
        store.update_row(
            "whatsapp_demo_sessions",
            session["id"],
            {
                "status": "active",
                "judge_phone_hash": protected.lookup_hash,
                "judge_phone_encrypted": protected.encrypted,
            },
        )
    )
    headers = {
        **AUTH,
        "X-OBLIQ-Demo-Session-Id": session["id"],
        "X-OBLIQ-Demo-Access-Token": created["dashboard_access_token"],
    }
    request = client.post(
        f"/api/v1/applications/{APP_ID}/document-request/draft", headers=headers
    )
    assert request.status_code == 201
    links_before = asyncio.run(store.list_rows("upload_links"))
    requirements = asyncio.run(
        store.list_rows(
            "document_requirements",
            {"application_id": session["session_application_id"]},
            order="label",
        )
    )
    for requirement in requirements[:-1]:
        asyncio.run(
            store.update_row(
                "document_requirements", requirement["id"], {"status": "received"}
            )
        )

    reminder = client.post(
        f"/api/v1/applications/{APP_ID}/reminders/draft", headers=headers
    )

    collection = client.get(
        f"/api/v1/applications/{APP_ID}/document-collection-status",
        headers=headers,
    )

    assert reminder.status_code == 201, reminder.text
    assert collection.status_code == 200, collection.text
    assert collection.json()["received_count"] == len(requirements) - 1
    assert collection.json()["effective_application_id"] == session["session_application_id"]
    assert requirements[-1]["label"] in reminder.json()["draft_message"]
    for requirement in requirements[:-1]:
        assert requirement["label"] not in reminder.json()["draft_message"]
    assert "existing secure upload link" in reminder.json()["draft_message"]
    assert len(asyncio.run(store.list_rows("upload_links"))) == len(links_before)
