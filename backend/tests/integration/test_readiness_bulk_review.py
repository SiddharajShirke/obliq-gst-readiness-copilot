import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.repositories import get_store
from app.repositories.memory import DEMO_FIRM_ID

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}
APP_ID = "30000000-0000-0000-0000-000000000001"
OTHER_APP_ID = "30000000-0000-0000-0000-000000000002"


def test_bulk_validation_review_is_scoped_and_reaches_ready_for_filing() -> None:
    store = get_store()
    asyncio.run(store.reset_demo())
    asyncio.run(store.update_row("applications", APP_ID, {"status": "validation_review"}))
    findings = [
        asyncio.run(
            store.insert_row(
                "validation_findings",
                {
                    "id": f"bulk-validation-{index}",
                    "firm_id": DEMO_FIRM_ID,
                    "application_id": APP_ID,
                    "finding_type": "missing_field",
                    "severity": "medium",
                    "message": f"Finding {index}",
                    "status": "open",
                },
            )
        )
        for index in (1, 2)
    ]
    response = client.post(
        f"/api/v1/applications/{APP_ID}/findings/bulk-review",
        headers=AUTH,
        json={"finding_ids": [row["id"] for row in findings], "status": "resolved"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["updated_count"] == 2
    assert response.json()["workflow"]["readiness"]["ready_for_filing"] is True
    assert asyncio.run(store.get_row("applications", APP_ID))["status"] == "ready_for_filing"
    actions = {
        row["action"]
        for row in asyncio.run(store.list_rows("audit_events", {"application_id": APP_ID}))
    }
    assert "bulk_validation_review" in actions
    assert "validation_review_completed" in actions
    assert "ready_for_filing_reached" in actions
    export = client.post(f"/api/v1/applications/{APP_ID}/export", headers=AUTH)
    assert export.status_code == 200, export.text
    assert "preparatory_report_pdf" in export.json()


def test_bulk_validation_review_rejects_cross_application_ids_atomically() -> None:
    store = get_store()
    asyncio.run(store.reset_demo())
    local = asyncio.run(
        store.insert_row(
            "validation_findings",
            {
                "id": "local-finding",
                "firm_id": DEMO_FIRM_ID,
                "application_id": APP_ID,
                "finding_type": "test",
                "severity": "low",
                "message": "Local",
                "status": "open",
            },
        )
    )
    foreign = asyncio.run(
        store.insert_row(
            "validation_findings",
            {
                "id": "foreign-finding",
                "firm_id": DEMO_FIRM_ID,
                "application_id": OTHER_APP_ID,
                "finding_type": "test",
                "severity": "low",
                "message": "Foreign",
                "status": "open",
            },
        )
    )
    response = client.post(
        f"/api/v1/applications/{APP_ID}/findings/bulk-review",
        headers=AUTH,
        json={"finding_ids": [local["id"], foreign["id"]], "status": "accepted"},
    )
    assert response.status_code == 404
    assert asyncio.run(store.get_row("validation_findings", local["id"]))["status"] == "open"


def test_main_export_is_blocked_until_validation_is_complete() -> None:
    store = get_store()
    asyncio.run(store.reset_demo())
    asyncio.run(store.update_row("applications", APP_ID, {"status": "validation_review"}))
    asyncio.run(
        store.insert_row(
            "validation_findings",
            {
                "id": "blocking-export-finding",
                "firm_id": DEMO_FIRM_ID,
                "application_id": APP_ID,
                "finding_type": "test",
                "severity": "medium",
                "message": "Pending CA review",
                "status": "open",
            },
        )
    )

    response = client.post(f"/api/v1/applications/{APP_ID}/export", headers=AUTH)

    assert response.status_code == 409
    assert "Complete Validation Review" in response.json()["detail"]


def test_repeated_main_exports_use_unique_generation_paths() -> None:
    store = get_store()
    asyncio.run(store.reset_demo())
    asyncio.run(store.update_row("applications", APP_ID, {"status": "validation_review"}))

    first = client.post(f"/api/v1/applications/{APP_ID}/export", headers=AUTH)
    second = client.post(f"/api/v1/applications/{APP_ID}/export", headers=AUTH)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert "export_pack_zip" in first.json()
    assert first.json()["export_pack_zip"] != second.json()["export_pack_zip"]


def test_bulk_reconciliation_review_updates_only_pending_review_findings() -> None:
    store = get_store()
    asyncio.run(store.reset_demo())
    run = asyncio.run(
        store.insert_row(
            "reconciliation_runs",
            {
                "id": "bulk-recon-run",
                "firm_id": DEMO_FIRM_ID,
                "application_id": APP_ID,
                "status": "completed",
                "created_at": "2026-08-23T12:00:00+00:00",
            },
        )
    )
    mismatch = asyncio.run(
        store.insert_row(
            "reconciliation_items",
            {
                "id": "bulk-recon-mismatch",
                "reconciliation_run_id": run["id"],
                "match_status": "value_mismatch",
                "review_status": "pending",
            },
        )
    )
    exact = asyncio.run(
        store.insert_row(
            "reconciliation_items",
            {
                "id": "bulk-recon-exact",
                "reconciliation_run_id": run["id"],
                "match_status": "exact_match",
                "review_status": "pending",
            },
        )
    )

    response = client.post(
        f"/api/v1/applications/{APP_ID}/reconciliation/items/bulk-review",
        headers=AUTH,
        json={"item_ids": [mismatch["id"]], "action": "mark_reviewed"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["updated_count"] == 1
    assert response.json()["workflow"]["reconciliation"]["progress_percent"] == 100
    assert response.json()["workflow"]["reconciliation"]["export_enabled"] is True
    assert (
        asyncio.run(store.get_row("reconciliation_items", exact["id"]))["review_status"]
        == "pending"
    )

    ineligible = client.post(
        f"/api/v1/applications/{APP_ID}/reconciliation/items/bulk-review",
        headers=AUTH,
        json={"item_ids": [exact["id"]], "action": "mark_reviewed"},
    )
    assert ineligible.status_code == 409
