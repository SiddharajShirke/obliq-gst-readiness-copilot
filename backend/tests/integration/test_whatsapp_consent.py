from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}


def test_outbound_whatsapp_requires_client_consent() -> None:
    created_client = client.post(
        "/api/v1/clients",
        headers=AUTH,
        json={
            "business_name": "Consent Pending Traders",
            "legal_name": "Consent Pending Traders",
            "gstin": "27CONSE1234A1Z5",
            "state": "Maharashtra",
            "business_type": "Retail",
            "filing_frequency": "monthly",
            "contact_name": "Consent Pending",
            "whatsapp_phone": "+919866666666",
            "preferred_language": "English",
            "whatsapp_consent": False,
        },
    )
    assert created_client.status_code == 201, created_client.text

    application = client.post(
        f"/api/v1/clients/{created_client.json()['id']}/applications",
        headers=AUTH,
        json={
            "financial_year": "2026-27",
            "period_label": "May 2026",
            "period_start": "2026-05-01",
            "period_end": "2026-05-31",
            "filing_frequency": "monthly",
            "due_date": "2026-06-20",
        },
    )
    assert application.status_code == 201, application.text

    draft = client.post(
        f"/api/v1/applications/{application.json()['id']}/document-request/draft",
        headers=AUTH,
    )
    assert draft.status_code == 201, draft.text

    send = client.post(
        f"/api/v1/applications/{application.json()['id']}/document-request/approve-send",
        headers=AUTH,
        json={"reminder_id": draft.json()["id"], "message": draft.json()["draft_message"]},
    )

    assert send.status_code == 409
    assert "consent" in send.json()["detail"].lower()
