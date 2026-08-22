from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.repositories import get_store
from app.repositories.memory import DEMO_ADMIN_ID, MemoryStore
from app.services.secure_upload import create_secure_upload_link
from app.services.whatsapp.cleanup import cleanup_demo_sessions
from app.services.whatsapp.sessions import create_demo_session

APP_ID = "30000000-0000-0000-0000-000000000001"
AUTH = {"Authorization": "Bearer demo-admin-token"}


@pytest.fixture
def phase2_client(tmp_path):
    settings = Settings(
        app_env="test",
        whatsapp_provider="mock",
        upload_token_pepper="upload-pepper",
        allowed_upload_extensions="pdf,png,jpg,jpeg,csv,xlsx,docx,json",
        local_upload_dir=tmp_path / "uploads",
        whatsapp_demo_token_pepper="token-pepper",
        whatsapp_phone_hash_pepper="phone-pepper",
        whatsapp_phone_encryption_key=Fernet.generate_key().decode(),
        vonage_whatsapp_from="14155238886",
        vonage_sandbox_join_message="join obliq-demo",
        public_base_url="https://api.example.com",
        frontend_url="https://dashboard.example.com",
        _env_file=None,
    )
    store = MemoryStore(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client, store, settings
    app.dependency_overrides.clear()


async def _active_demo_link(store: MemoryStore, settings: Settings):
    created = await create_demo_session(store, settings, APP_ID, DEMO_ADMIN_ID)
    await store.update_row(
        "whatsapp_demo_sessions",
        created.session_id,
        {
            "status": "active",
            "connected_at": datetime.now(UTC).isoformat(),
        },
    )
    session = await store.get_row("whatsapp_demo_sessions", created.session_id)
    application = await store.get_row("applications", created.session_application_id)
    assert session is not None and application is not None
    link = await create_secure_upload_link(
        store,
        settings,
        application=application,
        demo_session=session,
        created_by_user_id=DEMO_ADMIN_ID,
    )
    return created, session, application, link


def _pdf() -> bytes:
    return b"%PDF-1.7\nSynthetic GST register only\n%%EOF"


def test_demo_upload_is_private_awaiting_processing_and_isolated(phase2_client) -> None:
    client, store, settings = phase2_client
    created, session, application, link = asyncio.run(
        _active_demo_link(store, settings)
    )
    other = asyncio.run(create_demo_session(store, settings, APP_ID, DEMO_ADMIN_ID))
    clone_requirements = asyncio.run(
        store.list_rows(
            "document_requirements",
            {"application_id": created.session_application_id},
            order="label",
        )
    )
    requirement = next(
        row for row in clone_requirements if row["requirement_type"] == "sales_register"
    )
    public_context = client.get(f"/api/v1/public/upload/{link.raw_token}")
    assert public_context.status_code == 200
    assert set(public_context.json()) == {
        "firm",
        "client",
        "application",
        "checklist",
        "allowed_extensions",
        "maximum_size_mb",
    }
    assert set(public_context.json()["client"]) == {"business_name"}
    assert "token" not in public_context.text.lower()

    response = client.post(
        f"/api/v1/public/upload/{link.raw_token}",
        data={"requirement_id": requirement["id"]},
        files={"file": ("../Sales Register?.pdf", _pdf(), "application/pdf")},
    )

    assert response.status_code == 201, response.text
    public_result = response.json()
    assert set(public_result) == {
        "id",
        "requirement_id",
        "original_name",
        "upload_status",
        "processing_status",
    }
    assert public_result["upload_status"] == "uploaded"
    document = asyncio.run(store.get_row("documents", public_result["id"]))
    assert document is not None
    assert document["processing_status"] == "awaiting_processing"
    assert document["source"] == "secure_link"
    assert document["demo_session_id"] == created.session_id
    assert document["application_id"] == created.session_application_id
    assert document["requirement_id"] == requirement["id"]
    assert document["safe_name"] == "Sales_Register_.pdf"
    assert document["storage_bucket"] == settings.supabase_documents_bucket
    assert document["storage_path"] == (
        f"{session['firm_id']}/{session['base_client_id']}/{created.session_id}/"
        f"{created.session_application_id}/{document['id']}/Sales_Register_.pdf"
    )
    assert document["document_type"] is None
    assert document["upload_completed_at"] is not None
    assert asyncio.run(
        store.download_file(document["storage_bucket"], document["storage_path"])
    ) == _pdf()
    assert asyncio.run(
        store.list_rows("document_extractions", {"document_id": document["id"]})
    ) == []
    status = client.get(
        f"/api/v1/whatsapp-demo-sessions/{created.session_id}",
        headers={
            **AUTH,
            "X-OBLIQ-Demo-Access-Token": created.dashboard_access_token,
        },
    )
    assert status.status_code == 200, status.text
    sales_status = next(
        row for row in status.json()["checklist"] if row["id"] == requirement["id"]
    )
    assert sales_status["upload_status"] == "uploaded"
    assert sales_status["processing_status"] == "awaiting_processing"

    updated = asyncio.run(store.get_row("document_requirements", requirement["id"]))
    assert updated["status"] == "received"
    base = asyncio.run(
        store.list_rows(
            "document_requirements",
            {"application_id": APP_ID, "requirement_type": "sales_register"},
            limit=1,
        )
    )[0]
    other_requirement = asyncio.run(
        store.list_rows(
            "document_requirements",
            {
                "application_id": other.session_application_id,
                "requirement_type": "sales_register",
            },
            limit=1,
        )
    )[0]
    assert base["status"] == "missing"
    assert other_requirement["status"] == "missing"
    assert application["id"] != APP_ID
    actions = {
        row["action"] for row in asyncio.run(store.list_rows("audit_events"))
    }
    assert "checklist_requirement_received" in actions


def test_duplicate_and_cross_session_requirement_do_not_complete_checklist(
    phase2_client,
) -> None:
    client, store, settings = phase2_client
    first, _, _, link = asyncio.run(_active_demo_link(store, settings))
    second = asyncio.run(create_demo_session(store, settings, APP_ID, DEMO_ADMIN_ID))
    first_requirements = asyncio.run(
        store.list_rows("document_requirements", {"application_id": first.session_application_id})
    )
    first_sales = next(
        row for row in first_requirements if row["requirement_type"] == "sales_register"
    )
    first_purchase = next(
        row for row in first_requirements if row["requirement_type"] == "purchase_register"
    )
    second_requirement = asyncio.run(
        store.list_rows(
            "document_requirements",
            {"application_id": second.session_application_id},
            limit=1,
        )
    )[0]

    uploaded = client.post(
        f"/api/v1/public/upload/{link.raw_token}",
        data={"requirement_id": first_sales["id"]},
        files={"file": ("sales.pdf", _pdf(), "application/pdf")},
    )
    duplicate = client.post(
        f"/api/v1/public/upload/{link.raw_token}",
        data={"requirement_id": first_purchase["id"]},
        files={"file": ("same.pdf", _pdf(), "application/pdf")},
    )
    crossed = client.post(
        f"/api/v1/public/upload/{link.raw_token}",
        data={"requirement_id": second_requirement["id"]},
        files={"file": ("other.pdf", b"%PDF-1.7\nother", "application/pdf")},
    )

    assert uploaded.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "This file was already uploaded"
    assert crossed.status_code == 400
    actions = {
        row["action"] for row in asyncio.run(store.list_rows("audit_events"))
    }
    assert "upload_duplicate_rejected" in actions
    assert "upload_failed" in actions
    assert asyncio.run(store.get_row("document_requirements", first_purchase["id"]))[
        "status"
    ] == "missing"
    assert asyncio.run(store.get_row("document_requirements", second_requirement["id"]))[
        "status"
    ] == "missing"


def test_expired_revoked_and_invalid_files_change_no_document_state(
    phase2_client,
) -> None:
    client, store, settings = phase2_client
    created, _, _, link = asyncio.run(_active_demo_link(store, settings))
    requirement = asyncio.run(
        store.list_rows(
            "document_requirements",
            {"application_id": created.session_application_id},
            limit=1,
        )
    )[0]

    mismatch = client.post(
        f"/api/v1/public/upload/{link.raw_token}",
        data={"requirement_id": requirement["id"]},
        files={"file": ("invoice.pdf", b"%PDF-1.7", "image/png")},
    )
    assert mismatch.status_code == 400
    assert "upload_unsupported_rejected" in {
        row["action"] for row in asyncio.run(store.list_rows("audit_events"))
    }
    assert asyncio.run(store.list_rows("documents")) == []
    assert asyncio.run(store.get_row("document_requirements", requirement["id"]))[
        "status"
    ] == "missing"

    links = asyncio.run(store.list_rows("upload_links", {"token_hash": link.raw_token}))
    assert links == []
    link_rows = asyncio.run(store.list_rows("upload_links", {"id": link.id}))
    asyncio.run(
        store.update_row(
            "upload_links",
            link.id,
            {"expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()},
        )
    )
    expired = client.get(f"/api/v1/public/upload/{link.raw_token}")
    assert expired.status_code == 410
    assert "upload_token_expired" in {
        row["action"] for row in asyncio.run(store.list_rows("audit_events"))
    }

    asyncio.run(
        store.update_row(
            "upload_links",
            link.id,
            {
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                "revoked_at": datetime.now(UTC).isoformat(),
            },
        )
    )
    revoked = client.get(f"/api/v1/public/upload/{link.raw_token}")
    assert revoked.status_code == 410
    assert "upload_token_revoked" in {
        row["action"] for row in asyncio.run(store.list_rows("audit_events"))
    }
    assert link_rows[0]["demo_session_id"] == created.session_id


def test_malformed_and_cross_firm_upload_capabilities_are_rejected(
    phase2_client,
) -> None:
    client, store, settings = phase2_client
    _, _, _, link = asyncio.run(_active_demo_link(store, settings))

    malformed = client.get("/api/v1/public/upload/not-a-capability")
    assert malformed.status_code == 404

    asyncio.run(
        store.update_row(
            "upload_links",
            link.id,
            {"firm_id": "ffffffff-ffff-ffff-ffff-ffffffffffff"},
        )
    )
    crossed = client.get(f"/api/v1/public/upload/{link.raw_token}")
    assert crossed.status_code == 404
    assert "firm_id" not in crossed.text


def test_demo_cleanup_removes_private_upload_and_metadata(phase2_client) -> None:
    client, store, settings = phase2_client
    created, _, _, link = asyncio.run(_active_demo_link(store, settings))
    requirement = asyncio.run(
        store.list_rows(
            "document_requirements",
            {"application_id": created.session_application_id},
            limit=1,
        )
    )[0]
    uploaded = client.post(
        f"/api/v1/public/upload/{link.raw_token}",
        data={"requirement_id": requirement["id"]},
        files={"file": ("cleanup.pdf", _pdf(), "application/pdf")},
    )
    assert uploaded.status_code == 201
    document = asyncio.run(store.get_row("documents", uploaded.json()["id"]))
    assert document is not None
    old = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    asyncio.run(
        store.update_row(
            "whatsapp_demo_sessions",
            created.session_id,
            {"created_at": old, "expires_at": old, "status": "expired"},
        )
    )

    result = asyncio.run(cleanup_demo_sessions(store, settings))

    assert result["deleted"] == 1
    assert asyncio.run(store.get_row("documents", document["id"])) is None
    with pytest.raises(FileNotFoundError):
        asyncio.run(
            store.download_file(document["storage_bucket"], document["storage_path"])
        )
