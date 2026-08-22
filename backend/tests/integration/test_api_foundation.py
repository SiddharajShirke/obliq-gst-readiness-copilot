from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_reports_demo_dependencies() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] in {"memory", "supabase"}


def test_clients_reject_missing_bearer_token() -> None:
    response = client.get("/api/v1/clients")
    assert response.status_code == 401


def test_demo_admin_can_list_seeded_clients() -> None:
    response = client.get(
        "/api/v1/clients",
        headers={"Authorization": "Bearer demo-admin-token"},
    )
    assert response.status_code == 200
    names = {item["business_name"] for item in response.json()}
    assert {"Raj Traders", "ABC Electronics", "Nova Services"}.issubset(names)


def test_demo_admin_can_create_application_with_six_requirements() -> None:
    response = client.post(
        "/api/v1/clients/20000000-0000-0000-0000-000000000001/applications",
        headers={"Authorization": "Bearer demo-admin-token"},
        json={
            "financial_year": "2026-27",
            "period_label": "May 2026",
            "period_start": "2026-05-01",
            "period_end": "2026-05-31",
            "filing_frequency": "monthly",
            "due_date": "2026-06-20",
        },
    )
    assert response.status_code == 201
    application = response.json()
    checklist = client.get(
        f"/api/v1/applications/{application['id']}/checklist",
        headers={"Authorization": "Bearer demo-admin-token"},
    )
    assert checklist.status_code == 200
    assert len(checklist.json()) == 6


def test_seeded_quarterly_application_uses_quarter_dates() -> None:
    response = client.get(
        "/api/v1/applications/30000000-0000-0000-0000-000000000004",
        headers={"Authorization": "Bearer demo-admin-token"},
    )
    assert response.status_code == 200, response.text
    application = response.json()
    assert application["period_start"] == "2026-04-01"
    assert application["period_end"] == "2026-06-30"
    assert application["due_date"] == "2026-07-22"


def test_seeded_raj_walkthrough_starts_with_empty_checklist() -> None:
    response = client.get(
        "/api/v1/applications/30000000-0000-0000-0000-000000000001/checklist",
        headers={"Authorization": "Bearer demo-admin-token"},
    )
    assert response.status_code == 200, response.text
    assert len(response.json()) == 6
    assert all(row["status"] == "missing" for row in response.json())
