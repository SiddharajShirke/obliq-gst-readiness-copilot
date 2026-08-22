import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.repositories import get_store

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}
APP_ID = "30000000-0000-0000-0000-000000000001"


def _seed_correction_record():
    store = get_store()
    asyncio.run(store.reset_demo())
    document = asyncio.run(
        store.insert_row(
            "documents",
            {
                "id": "correction-doc",
                "firm_id": "11111111-1111-1111-1111-111111111111",
                "client_id": "20000000-0000-0000-0000-000000000001",
                "application_id": APP_ID,
                "original_name": "Purchase.csv",
                "storage_path": "test/Purchase.csv",
                "document_type": "purchase_register",
                "processing_status": "approved",
            },
        )
    )
    extraction = asyncio.run(
        store.insert_row(
            "document_extractions",
            {
                "id": "correction-extraction",
                "document_id": document["id"],
                "document_type": "purchase_register",
                "structured_data": {"rows": [{"document_number": "P-1", "taxable_value": "900"}]},
                "original_structured_data": {
                    "rows": [{"document_number": "P-1", "taxable_value": "900"}]
                },
                "review_status": "approved",
            },
        )
    )
    record = asyncio.run(
        store.insert_row(
            "invoice_records",
            {
                "id": "correction-record",
                "firm_id": document["firm_id"],
                "client_id": document["client_id"],
                "application_id": APP_ID,
                "document_id": document["id"],
                "document_type": "purchase_register",
                "invoice_category": "purchase",
                "invoice_number": "P-1",
                "taxable_value": "900",
                "cgst": "81",
                "sgst": "81",
                "total_tax": "162",
                "invoice_total": "1062",
                "review_status": "approved",
            },
        )
    )
    return store, extraction, record


def test_manual_correction_is_a_proposal_until_ca_applies_it() -> None:
    store, extraction, record = _seed_correction_record()
    proposed = client.post(
        f"/api/v1/applications/{APP_ID}/validation-corrections/proposals",
        headers=AUTH,
        json={"mode": "manual", "record_ids": [record["id"]], "changes": {"taxable_value": "950"}},
    )
    assert proposed.status_code == 201, proposed.text
    assert proposed.json()["status"] == "proposed"
    assert proposed.json()["changes"][0]["before"] == "900"
    assert proposed.json()["changes"][0]["after"] == "950"
    assert asyncio.run(store.get_row("invoice_records", record["id"]))["taxable_value"] == "900"

    applied = client.post(
        f"/api/v1/validation-corrections/{proposed.json()['id']}/apply", headers=AUTH
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["revalidation"]["eligible_record_count"] == 1
    assert asyncio.run(store.get_row("invoice_records", record["id"]))["taxable_value"] == "950"
    assert (
        asyncio.run(store.get_row("document_extractions", extraction["id"]))[
            "original_structured_data"
        ]["rows"][0]["taxable_value"]
        == "900"
    )


def test_mock_ai_correction_returns_read_only_nvidia_first_proposal() -> None:
    store, _, record = _seed_correction_record()
    response = client.post(
        f"/api/v1/applications/{APP_ID}/validation-corrections/proposals",
        headers=AUTH,
        json={"mode": "ai", "record_ids": [record["id"]], "changes": {}},
    )
    assert response.status_code == 201, response.text
    assert response.json()["proposal_type"] == "ai"
    assert response.json()["provider"] == "nvidia"
    assert response.json()["status"] == "proposed"
    assert asyncio.run(store.get_row("invoice_records", record["id"]))["taxable_value"] == "900"


def test_validation_alert_requires_explicit_ca_action_and_is_categorized() -> None:
    store, _, record = _seed_correction_record()
    validated = client.post(f"/api/v1/applications/{APP_ID}/validate", headers=AUTH)
    assert validated.status_code == 200
    assert asyncio.run(store.list_rows("alerts", {"application_id": APP_ID})) == []
    finding = validated.json()["findings"][0]

    raised = client.post(f"/api/v1/findings/{finding['id']}/raise-alert", headers=AUTH)
    assert raised.status_code == 201, raised.text
    assert raised.json()["workflow_area"] == "validation"
    assert raised.json()["alert_category"] == finding["finding_type"].upper()
    assert raised.json()["validation_finding_id"] == finding["id"]
