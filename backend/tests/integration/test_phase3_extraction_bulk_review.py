import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.repositories import get_store

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}
APP_ID = "30000000-0000-0000-0000-000000000001"
OTHER_APP_ID = "30000000-0000-0000-0000-000000000002"


def _seed_review_rows():
    store = get_store()
    asyncio.run(store.reset_demo())
    document = asyncio.run(
        store.insert_row(
            "documents",
            {
                "id": "bulk-review-document",
                "firm_id": "11111111-1111-1111-1111-111111111111",
                "client_id": "20000000-0000-0000-0000-000000000001",
                "application_id": APP_ID,
                "original_name": "Sales.csv",
                "storage_path": "test/Sales.csv",
                "document_type": "sales_register",
                "processing_status": "ready_for_review",
            },
        )
    )
    extraction = asyncio.run(
        store.insert_row(
            "document_extractions",
            {
                "id": "bulk-review-extraction",
                "document_id": document["id"],
                "document_type": "sales_register",
                "structured_data": {"rows": [{"document_number": "S-1"}]},
                "original_structured_data": {"rows": [{"document_number": "S-1"}]},
                "review_status": "pending",
            },
        )
    )
    records = []
    for index in (1, 2):
        records.append(
            asyncio.run(
                store.insert_row(
                    "invoice_records",
                    {
                        "id": f"bulk-review-record-{index}",
                        "firm_id": document["firm_id"],
                        "client_id": document["client_id"],
                        "application_id": APP_ID,
                        "document_id": document["id"],
                        "document_type": "sales_register",
                        "invoice_category": "sales",
                        "invoice_number": f"S-{index}",
                        "review_status": "pending",
                    },
                )
            )
        )
    return store, document, extraction, records


def test_bulk_review_approves_selected_records_and_preserves_original_extraction() -> None:
    store, document, extraction, records = _seed_review_rows()
    response = client.post(
        f"/api/v1/applications/{APP_ID}/extractions/bulk-review",
        headers=AUTH,
        json={
            "record_ids": [row["id"] for row in records],
            "action": "approve",
            "notes": "Checked",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["updated_count"] == 2
    assert all(
        asyncio.run(store.get_row("invoice_records", row["id"]))["review_status"] == "approved"
        for row in records
    )
    after_extraction = asyncio.run(store.get_row("document_extractions", extraction["id"]))
    assert after_extraction["review_status"] == "approved"
    assert after_extraction["original_structured_data"] == {"rows": [{"document_number": "S-1"}]}
    assert (
        asyncio.run(store.get_row("documents", document["id"]))["processing_status"] == "approved"
    )


def test_bulk_review_rejects_cross_application_record_ids() -> None:
    store, _, _, records = _seed_review_rows()
    foreign = asyncio.run(
        store.insert_row(
            "invoice_records",
            {
                "id": "foreign-review-record",
                "firm_id": "11111111-1111-1111-1111-111111111111",
                "client_id": "20000000-0000-0000-0000-000000000002",
                "application_id": OTHER_APP_ID,
                "document_id": "foreign-document",
                "invoice_category": "purchase",
                "review_status": "pending",
            },
        )
    )
    response = client.post(
        f"/api/v1/applications/{APP_ID}/extractions/bulk-review",
        headers=AUTH,
        json={"record_ids": [records[0]["id"], foreign["id"]], "action": "approve"},
    )
    assert response.status_code == 404
    assert (
        asyncio.run(store.get_row("invoice_records", records[0]["id"]))["review_status"]
        == "pending"
    )


def test_validation_uses_only_ca_approved_extraction_records() -> None:
    store, _, _, records = _seed_review_rows()
    asyncio.run(
        store.update_row("invoice_records", records[0]["id"], {"review_status": "approved"})
    )

    response = client.post(f"/api/v1/applications/{APP_ID}/validate", headers=AUTH)
    assert response.status_code == 200, response.text
    finding_record_ids = {item["invoice_record_id"] for item in response.json()["findings"]}
    assert records[0]["id"] in finding_record_ids
    assert records[1]["id"] not in finding_record_ids
    assert response.json()["eligible_record_count"] == 1
    assert response.json()["pending_review_count"] == 1
