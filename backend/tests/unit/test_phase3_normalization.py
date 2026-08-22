from decimal import Decimal
from io import BytesIO

import pandas as pd

from app.schemas.documents import NormalizedGSTRecord
from app.services.document_processing.parsers import parse_normalized_table


def _xlsx(rows: list[dict]) -> bytes:
    output = BytesIO()
    pd.DataFrame(rows).to_excel(output, index=False)
    return output.getvalue()


def test_purchase_register_normalizes_decimal_values_and_provenance() -> None:
    parsed = parse_normalized_table(
        _xlsx(
            [
                {
                    "Invoice No": "PTM/0826/220",
                    "Invoice Date": "2026-08-10",
                    "Supplier GSTIN": "27ABCDE1234F1Z5",
                    "Taxable Value": "90000.00",
                    "CGST": "8100.00",
                    "SGST": "8100.00",
                    "ITC Status": "available",
                    "RCM": "No",
                }
            ]
        ),
        ".xlsx",
        document_type="purchase_register",
        source_document_id="document-1",
        tax_period="August 2026",
    )
    row = parsed.records[0]
    assert row.document_number == "PTM/0826/220"
    assert row.taxable_value == Decimal("90000.00")
    assert row.total_tax == Decimal("16200.00")
    assert row.rcm_flag is False
    assert row.source_document_id == "document-1"
    assert row.source_row == 2


def test_missing_money_is_null_not_invented_zero() -> None:
    record = NormalizedGSTRecord(
        document_type="gst_special_transactions",
        source_document_id="document-2",
        source_row=1,
    )
    assert record.taxable_value is None
    assert record.total_tax is None
    assert record.total_document_value is None


def test_ai_record_normalizes_common_indian_date_to_iso_date() -> None:
    record = NormalizedGSTRecord.model_validate(
        {
            "document_type": "sales_register",
            "document_number": "INV-101",
            "document_date": "10-08-2026",
            "source_document_id": "document-3",
        }
    )

    assert record.document_date is not None
    assert record.document_date.isoformat() == "2026-08-10"
