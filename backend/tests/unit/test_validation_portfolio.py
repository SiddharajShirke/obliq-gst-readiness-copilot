import pytest

from app.config import Settings
from app.repositories.memory import DEMO_FIRM_ID, MemoryStore
from app.services.validation_portfolio import get_validation_portfolio

APP_ID = "30000000-0000-0000-0000-000000000001"
CLIENT_ID = "20000000-0000-0000-0000-000000000001"


@pytest.mark.asyncio
async def test_validation_portfolio_groups_live_findings_and_alerts_by_six_categories(
    tmp_path,
) -> None:
    store = MemoryStore(Settings(local_data_dir=tmp_path))
    requirement = (
        await store.list_rows(
            "document_requirements",
            {"application_id": APP_ID, "requirement_type": "purchase_register"},
        )
    )[0]
    await store.update_row("document_requirements", requirement["id"], {"status": "received"})
    document = await store.insert_row(
        "documents",
        {
            "id": "purchase-document",
            "firm_id": DEMO_FIRM_ID,
            "client_id": CLIENT_ID,
            "application_id": APP_ID,
            "requirement_id": requirement["id"],
            "document_type": "purchase_register",
            "processing_status": "approved",
        },
    )
    record = await store.insert_row(
        "invoice_records",
        {
            "id": "purchase-record",
            "firm_id": DEMO_FIRM_ID,
            "client_id": CLIENT_ID,
            "application_id": APP_ID,
            "document_id": document["id"],
            "document_type": "purchase_register",
            "review_status": "approved",
        },
    )
    finding = await store.insert_row(
        "validation_findings",
        {
            "id": "purchase-finding",
            "firm_id": DEMO_FIRM_ID,
            "application_id": APP_ID,
            "document_id": document["id"],
            "invoice_record_id": record["id"],
            "finding_type": "tax_arithmetic_mismatch",
            "severity": "high",
            "message": "Tax arithmetic differs",
            "status": "open",
        },
    )
    await store.insert_row(
        "alerts",
        {
            "id": "purchase-alert",
            "firm_id": DEMO_FIRM_ID,
            "client_id": CLIENT_ID,
            "application_id": APP_ID,
            "validation_finding_id": finding["id"],
            "workflow_area": "validation",
            "alert_type": "TAX_ARITHMETIC_MISMATCH",
            "title": "Tax arithmetic mismatch",
            "severity": "high",
            "status": "open",
        },
    )

    portfolio = await get_validation_portfolio(store, APP_ID)

    assert len(portfolio["categories"]) == 6
    purchase = next(item for item in portfolio["categories"] if item["type"] == "purchase_register")
    assert purchase["requirement_status"] == "received"
    assert purchase["record_count"] == 1
    assert purchase["approved_record_count"] == 1
    assert purchase["finding_count"] == 1
    assert purchase["alert_count"] == 1
    assert purchase["finding_groups"] == [
        {
            "type": "tax_arithmetic_mismatch",
            "label": "Tax Arithmetic Mismatch",
            "count": 1,
            "open_count": 1,
        }
    ]
    assert portfolio["summary"]["finding_count"] == 1
    assert all(
        item["type"] not in {"gstr2b", "developer_ground_truth"} for item in portfolio["categories"]
    )
