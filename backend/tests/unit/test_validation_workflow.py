from __future__ import annotations

from datetime import date

import pytest

from app.config import Settings
from app.repositories.memory import MemoryStore
from app.services.validation_workflow import advance_after_extraction_review

FIRM_ID = "11111111-1111-1111-1111-111111111111"
CLIENT_ID = "20000000-0000-0000-0000-000000000001"
APP_ID = "30000000-0000-0000-0000-000000000001"


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore(Settings(app_env="test", use_in_memory_db=True, _env_file=None))


async def _seed_scope(store: MemoryStore) -> None:
    await store.insert_row(
        "clients",
        {
            "id": CLIENT_ID,
            "firm_id": FIRM_ID,
            "business_name": "Dynamic Validation Client",
            "gstin": "27ABCDE1234F1Z5",
        },
    )
    await store.insert_row(
        "applications",
        {
            "id": APP_ID,
            "firm_id": FIRM_ID,
            "client_id": CLIENT_ID,
            "period_start": date(2026, 5, 1).isoformat(),
            "period_end": date(2026, 5, 31).isoformat(),
            "period_label": "May 2026",
            "status": "extraction_review",
        },
    )


async def _record(
    store: MemoryStore,
    *,
    record_id: str,
    review_status: str,
    invoice_date: str,
) -> dict:
    return await store.insert_row(
        "invoice_records",
        {
            "id": record_id,
            "firm_id": FIRM_ID,
            "client_id": CLIENT_ID,
            "application_id": APP_ID,
            "document_id": f"document-{record_id}",
            "invoice_category": "purchase",
            "document_type": "purchase_register",
            "invoice_number": record_id,
            "invoice_date": invoice_date,
            "supplier_gstin": "29ABCDE1234F1Z3",
            "taxable_value": "1000.00",
            "cgst": "90.00",
            "sgst": "90.00",
            "igst": "0.00",
            "cess": "0.00",
            "invoice_total": "1180.00",
            "review_status": review_status,
        },
    )


@pytest.mark.asyncio
async def test_pending_record_keeps_application_in_extraction_review(
    store: MemoryStore,
) -> None:
    await _seed_scope(store)
    await _record(
        store,
        record_id="approved-record",
        review_status="approved",
        invoice_date="2026-05-10",
    )
    await _record(
        store,
        record_id="pending-record",
        review_status="pending",
        invoice_date="2026-06-10",
    )

    result = await advance_after_extraction_review(
        store,
        application_id=APP_ID,
        firm_id=FIRM_ID,
    )

    assert result.current_stage == "extraction_review"
    assert result.validation_ran is False
    assert result.approved_record_count == 1
    assert result.pending_record_count == 1
    assert await store.list_rows("validation_findings", {"application_id": APP_ID}) == []
    assert (await store.get_row("applications", APP_ID))["status"] == "extraction_review"


@pytest.mark.asyncio
async def test_final_review_validates_approved_records_and_excludes_rejected(
    store: MemoryStore,
) -> None:
    await _seed_scope(store)
    approved = await _record(
        store,
        record_id="approved-outside-period",
        review_status="approved",
        invoice_date="2026-06-10",
    )
    rejected = await _record(
        store,
        record_id="rejected-outside-period",
        review_status="rejected",
        invoice_date="2026-06-11",
    )

    result = await advance_after_extraction_review(
        store,
        application_id=APP_ID,
        firm_id=FIRM_ID,
    )

    assert result.current_stage == "validation_review"
    assert result.validation_ran is True
    assert result.approved_record_count == 1
    assert result.rejected_record_count == 1
    assert result.pending_record_count == 0
    assert result.eligible_record_count == 1
    assert result.findings
    assert {row["invoice_record_id"] for row in result.findings} == {approved["id"]}
    assert rejected["id"] not in {row["invoice_record_id"] for row in result.findings}
    assert (await store.get_row("applications", APP_ID))["status"] == "validation_review"


@pytest.mark.asyncio
async def test_gstr2b_records_are_excluded_from_client_document_validation(
    store: MemoryStore,
) -> None:
    await _seed_scope(store)
    await _record(
        store,
        record_id="approved-client",
        review_status="approved",
        invoice_date="2026-05-10",
    )
    await store.insert_row(
        "invoice_records",
        {
            "id": "approved-gstr2b",
            "firm_id": FIRM_ID,
            "client_id": CLIENT_ID,
            "application_id": APP_ID,
            "document_id": "gstr2b-document",
            "source_type": "gstr2b",
            "document_type": "Tax Invoice",
            "invoice_number": "2B-1",
            "invoice_date": "2026-06-10",
            "review_status": "approved",
        },
    )

    result = await advance_after_extraction_review(
        store,
        application_id=APP_ID,
        firm_id=FIRM_ID,
    )

    assert result.eligible_record_count == 1
    assert "approved-gstr2b" not in {item.get("invoice_record_id") for item in result.findings}
