from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}


def test_firm_admin_cannot_publish_cross_tenant_official_knowledge() -> None:
    response = client.post(
        "/api/v1/knowledge/ingest",
        headers=AUTH,
        json={
            "title": "Unverified shared guidance",
            "text": "This text must stay private to the firm unless seeded by a trusted operator.",
            "source_type": "official_gst",
            "shared_official": True,
        },
    )

    assert response.status_code == 403
    assert "shared official" in response.json()["detail"].lower()
