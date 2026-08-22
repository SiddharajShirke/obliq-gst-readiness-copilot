import asyncio
import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import app
from app.repositories import get_store

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}
APP_ID = "30000000-0000-0000-0000-000000000001"


def test_reconciliation_item_requires_explicit_raise_alert_action() -> None:
    store = get_store()
    run = asyncio.run(
        store.insert_row(
            "reconciliation_runs",
            {
                "id": str(uuid.uuid4()),
                "firm_id": "11111111-1111-1111-1111-111111111111",
                "application_id": APP_ID,
                "status": "completed",
                "summary": {"value_mismatch": 1},
                "started_at": datetime.now(UTC).isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
                "created_by": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            },
        )
    )
    item = asyncio.run(
        store.insert_row(
            "reconciliation_items",
            {
                "id": str(uuid.uuid4()),
                "reconciliation_run_id": run["id"],
                "purchase_invoice_id": None,
                "gstr2b_invoice_id": None,
                "match_status": "value_mismatch",
                "match_score": "0.8",
                "differences": {
                    "taxable_value": {
                        "books": "90000.00",
                        "gstr2b": "95000.00",
                        "difference": "-5000.00",
                    }
                },
                "evidence": {
                    "books": {"invoice_number": "EFI/0826/889", "taxable_value": "90000.00"},
                    "gstr2b": {"invoice_number": "EFI/0826/889", "taxable_value": "95000.00"},
                    "difference_fields": ["taxable_value"],
                },
                "special_flags": [],
                "review_status": "pending",
            },
        )
    )

    before = client.get("/api/v1/alerts", headers=AUTH)
    assert before.status_code == 200
    assert not any(row.get("reconciliation_item_id") == item["id"] for row in before.json())

    raised = client.post(f"/api/v1/reconciliation/items/{item['id']}/raise-alert", headers=AUTH)
    assert raised.status_code == 201, raised.text
    alert = raised.json()
    assert alert["reconciliation_item_id"] == item["id"]
    assert alert["alert_type"] == "TAXABLE_VALUE_MISMATCH"
    assert alert["evidence"]["books"]["taxable_value"] == "90000.00"

    after = client.get("/api/v1/alerts", headers=AUTH)
    assert any(row["id"] == alert["id"] for row in after.json())
