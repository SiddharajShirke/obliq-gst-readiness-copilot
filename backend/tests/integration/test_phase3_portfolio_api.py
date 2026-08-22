from fastapi.testclient import TestClient

from app.main import app
from app.repositories import get_store

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}
APP_ID = "30000000-0000-0000-0000-000000000001"


def test_portfolio_endpoint_is_application_scoped_and_validates_scope() -> None:
    store = get_store()
    import asyncio

    asyncio.run(store.reset_demo())
    asyncio.run(
        store.insert_row(
            "invoice_records",
            {
                "id": "portfolio-sale-1",
                "application_id": APP_ID,
                "document_id": "portfolio-doc-1",
                "document_type": "sales_register",
                "invoice_category": "sales_register",
                "taxable_value": "1200.00",
                "total_tax": "216.00",
                "invoice_total": "1416.00",
                "review_status": "pending",
            },
        )
    )

    response = client.get(
        f"/api/v1/applications/{APP_ID}/documents/portfolio?scope=sales_register",
        headers=AUTH,
    )
    assert response.status_code == 200, response.text
    assert response.json()["scope"] == "sales_register"
    assert response.json()["summary"]["record_count"] == 1
    assert response.json()["records"][0]["id"] == "portfolio-sale-1"

    invalid = client.get(
        f"/api/v1/applications/{APP_ID}/documents/portfolio?scope=developer_ground_truth",
        headers=AUTH,
    )
    assert invalid.status_code == 422
