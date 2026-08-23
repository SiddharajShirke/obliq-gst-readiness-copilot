import json
from datetime import date
from decimal import Decimal

import pytest

from app.api.v1.compliance import run_reconciliation
from app.schemas.auth import UserContext
from app.services.reconciliation import ReconciliationRecord, reconcile_records

GSTIN = "27ABCDE1234F1Z5"


def record(
    record_id: str,
    number: str,
    taxable: str,
    *,
    gstin: str = GSTIN,
    invoice_date: date = date(2026, 8, 10),
    cgst: str = "0",
    sgst: str = "0",
    igst: str = "0",
    cess: str = "0",
    itc_status: str | None = None,
    rcm_flag: bool | None = None,
) -> ReconciliationRecord:
    return ReconciliationRecord(
        record_id=record_id,
        supplier_gstin=gstin,
        invoice_number=number,
        invoice_date=invoice_date,
        taxable_value=Decimal(taxable),
        cgst=Decimal(cgst),
        sgst=Decimal(sgst),
        igst=Decimal(igst),
        cess=Decimal(cess),
        itc_status=itc_status,
        rcm_flag=rcm_flag,
    )


def test_required_synthetic_outcomes_are_derived_without_ground_truth() -> None:
    books = [
        record("b1", "PTM/0826/220", "100000"),
        record("b2", "EFI/0826/889", "90000"),
        record("b3", "FC/0826/880", "70000", cgst="6300", sgst="6300"),
        record("b4", "PGH/0826/155", "50000"),
        record("b5", "BLA/0826/066", "40000", rcm_flag=True),
    ]
    gstr2b = [
        record("g1", "PTM/0826/220", "100000"),
        record("g2", "EFI/0826/889", "95000"),
        record("g3", "FC/0826/808", "70000", cgst="6300", sgst="6300"),
        record("g4", "SH/0826/332", "20000"),
        record("g5", "PGH/0826/155", "50000", itc_status="not_available"),
        record("g6", "BLA/0826/066", "40000", rcm_flag=True),
    ]

    result = reconcile_records(books, gstr2b)
    by_books = {
        item.purchase_record.invoice_number: item for item in result.items if item.purchase_record
    }
    assert by_books["PTM/0826/220"].match_status == "exact_match"
    assert by_books["EFI/0826/889"].match_status == "value_mismatch"
    assert by_books["EFI/0826/889"].differences["taxable_value"] == {
        "books": "90000.00",
        "gstr2b": "95000.00",
        "difference": "-5000.00",
    }
    assert by_books["FC/0826/880"].match_status == "invoice_number_mismatch"
    assert "itc_not_available" in by_books["PGH/0826/155"].special_flags
    assert "rcm" in by_books["BLA/0826/066"].special_flags
    assert any(
        item.match_status == "gstr2b_only"
        and item.gstr2b_record
        and item.gstr2b_record.invoice_number == "SH/0826/332"
        for item in result.items
    )


def test_no_monetary_tolerance_is_applied() -> None:
    result = reconcile_records(
        [record("b", "ONE", "100.00")],
        [record("g", "ONE", "100.01")],
    )
    assert result.items[0].match_status == "value_mismatch"


def test_ambiguous_stage_two_candidates_are_not_guessed() -> None:
    books = [record("b", "BOOKS-NO", "100")]
    gstr2b = [
        record("g1", "GSTR-NO-1", "100"),
        record("g2", "GSTR-NO-2", "100"),
    ]
    result = reconcile_records(books, gstr2b)
    assert result.items[0].match_status == "ambiguous_match"
    assert result.items[0].gstr2b_record is None


@pytest.mark.asyncio
async def test_reconciliation_persistence_payload_is_json_serializable() -> None:
    application_id = "application-id"
    firm_id = "firm-id"

    class JsonBoundaryStore:
        def __init__(self) -> None:
            self.inserted: list[tuple[str, dict]] = []

        async def get_row(self, table: str, row_id: str):
            if table == "applications" and row_id == application_id:
                return {
                    "id": application_id,
                    "firm_id": firm_id,
                    "client_id": "client-id",
                    "status": "ready_for_filing",
                }
            return None

        async def list_rows(self, table: str, filters=None, **kwargs):
            if table != "invoice_records":
                return []
            common = {
                "application_id": application_id,
                "supplier_gstin": GSTIN,
                "invoice_number": "INV-1",
                "invoice_date": "2026-08-10",
                "taxable_value": "1000.00",
                "cgst": "90.00",
                "sgst": "90.00",
                "igst": None,
                "cess": None,
                "invoice_total": "1180.00",
                "itc_status": None,
                "rcm_flag": False,
                "transaction_type": None,
            }
            return [
                {"id": "books-id", "invoice_category": "purchase", **common},
                {"id": "gstr2b-id", "invoice_category": "gstr2b", **common},
            ]

        async def insert_row(self, table: str, data: dict):
            json.dumps(data)
            self.inserted.append((table, data))
            return {"id": f"{table}-id", **data}

        async def update_row(self, table: str, row_id: str, data: dict):
            return {"id": row_id, **data}

    store = JsonBoundaryStore()
    result = await run_reconciliation(
        application_id,
        UserContext(user_id="user-id", firm_id=firm_id, role="firm_admin", email="a@b.test"),
        store,
    )

    assert result["items"][0]["match_status"] == "exact_match"
    persisted = next(data for table, data in store.inserted if table == "reconciliation_items")
    assert persisted["match_score"] == "1"
