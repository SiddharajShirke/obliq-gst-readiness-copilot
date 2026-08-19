from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}


def test_demo_admin_can_restore_seeded_memory_state() -> None:
    created = client.post(
        "/api/v1/clients",
        headers=AUTH,
        json={
            "business_name": "Temporary Demo Client",
            "legal_name": "Temporary Demo Client",
            "gstin": "27TEMPD1234A1Z5",
            "state": "Maharashtra",
            "business_type": "Retail",
            "filing_frequency": "monthly",
            "contact_name": "Temporary Contact",
            "whatsapp_phone": "+919877777777",
            "preferred_language": "English",
            "whatsapp_consent": True,
        },
    )
    assert created.status_code == 201, created.text

    before_reset = client.get("/api/v1/clients", headers=AUTH)
    assert len(before_reset.json()) >= 6

    reset = client.post("/api/v1/demo/reset", headers=AUTH)
    assert reset.status_code == 200, reset.text
    assert reset.json() == {"status": "reset", "clients": 5, "applications": 5}

    after_reset = client.get("/api/v1/clients", headers=AUTH)
    assert len(after_reset.json()) == 5
    assert all(row["business_name"] != "Temporary Demo Client" for row in after_reset.json())
