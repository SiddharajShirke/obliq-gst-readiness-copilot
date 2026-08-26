from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_reports_demo_dependencies() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] in {"memory", "supabase"}
    assert payload["embedding_warmup_enabled"] is False
    assert payload["frontend_origin"] == "http://localhost:3000"
    assert payload["live_upload_origin_ready"] is False
    assert isinstance(payload["uptime_seconds"], int)
    assert "release" in payload


def test_clients_reject_missing_bearer_token() -> None:
    response = client.get("/api/v1/clients")
    assert response.status_code == 401


def test_demo_admin_has_exactly_one_guided_demo_template() -> None:
    response = client.get(
        "/api/v1/clients",
        headers={"Authorization": "Bearer demo-admin-token"},
    )
    assert response.status_code == 200
    assert [item["business_name"] for item in response.json()] == ["Raj Traders"]
    assert response.json()[0]["demo_scenario"] == "guided_demo_template"


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


def test_seeded_raj_walkthrough_starts_with_empty_checklist() -> None:
    response = client.get(
        "/api/v1/applications/30000000-0000-0000-0000-000000000001/checklist",
        headers={"Authorization": "Bearer demo-admin-token"},
    )
    assert response.status_code == 200, response.text
    assert len(response.json()) == 6
    assert all(row["status"] == "missing" for row in response.json())


def test_application_list_uses_live_workflow_status() -> None:
    applications = client.get(
        "/api/v1/applications",
        headers={"Authorization": "Bearer demo-admin-token"},
    )

    assert applications.status_code == 200, applications.text
    raj = next(
        row
        for row in applications.json()
        if row["id"] == "30000000-0000-0000-0000-000000000001"
    )
    assert raj["display_status"] == "not_started"
    assert raj["workflow_percent"] == 0
