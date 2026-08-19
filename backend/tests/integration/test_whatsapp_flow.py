from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}
APP_ID = "30000000-0000-0000-0000-000000000001"
CLIENT_ID = "20000000-0000-0000-0000-000000000001"


def test_ca_approved_document_request_reaches_mock_client() -> None:
    draft = client.post(f"/api/v1/applications/{APP_ID}/document-request/draft", headers=AUTH)
    assert draft.status_code == 201
    payload = draft.json()
    assert payload["status"] == "awaiting_approval"
    assert "Purchase Register" in payload["draft_message"]

    sent = client.post(
        f"/api/v1/applications/{APP_ID}/document-request/approve-send",
        headers=AUTH,
        json={"reminder_id": payload["id"]},
    )
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"

    messages = client.get(f"/api/v1/demo/messages?client_id={CLIENT_ID}")
    assert messages.status_code == 200
    assert any("Purchase Register" in (message.get("content") or "") for message in messages.json())


def test_meta_webhook_verification_endpoint() -> None:
    response = client.get(
        "/api/v1/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "obliq-local-verify-token",
            "hub.challenge": "123456",
        },
    )
    assert response.status_code == 200
    assert response.text == "123456"
