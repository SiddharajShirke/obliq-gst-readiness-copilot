from datetime import date
from decimal import Decimal

from app.services.reconciliation import ReconciliationRecord, reconcile_records


def item(number: str, amount: str, invoice_date: date = date(2026, 4, 10)) -> ReconciliationRecord:
    return ReconciliationRecord(
        record_id=number,
        supplier_gstin="27ABCDE1234F1Z5",
        invoice_number=number,
        invoice_date=invoice_date,
        taxable_value=Decimal(amount),
        cgst=Decimal("90"),
        sgst=Decimal("90"),
        igst=Decimal("0"),
    )


def test_reconciliation_finds_match_mismatch_and_unmatched_records() -> None:
    purchase = [item("P-1", "1000"), item("P-2", "2000"), item("P-3", "3000")]
    gstr2b = [item("P-1", "1000"), item("P-2", "2100"), item("G-ONLY", "500")]

    result = reconcile_records(purchase, gstr2b)

    counts = result.summary
    assert counts["matched"] == 1
    assert counts["amount_mismatch"] == 1
    assert counts["purchase_only"] == 1
    assert counts["gstr2b_only"] == 1
