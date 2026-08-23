from decimal import Decimal
from io import BytesIO

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from app.schemas.documents import NormalizedGSTRecord
from app.services.document_processing.parsers import (
    parse_normalized_pdf_tables,
    parse_normalized_table,
)


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


def test_ai_record_discards_invalid_provenance_without_discarding_gst_data() -> None:
    record = NormalizedGSTRecord.model_validate(
        {
            "document_type": "gst_special_transactions",
            "document_number": "RCM/0826/001",
            "taxable_value": "12500.00",
            "source_document_id": "document-id",
            "source_page": " 3 ",
            "source_row": "A",
        }
    )

    assert record.document_number == "RCM/0826/001"
    assert record.taxable_value == Decimal("12500.00")
    assert record.source_page == 3
    assert record.source_row is None


def test_ai_record_normalizes_display_formatted_money_without_inventing_values() -> None:
    record = NormalizedGSTRecord.model_validate(
        {
            "document_type": "purchase_register",
            "source_document_id": "document-id",
            "taxable_value": "₹1,25,000.50",
            "gst_rate": "18%",
            "total_tax": "N/A",
            "document_date": "not visible",
        }
    )

    assert record.taxable_value == Decimal("125000.50")
    assert record.gst_rate == Decimal("18")
    assert record.total_tax is None
    assert record.document_date is None


def test_text_pdf_register_uses_deterministic_table_extraction() -> None:
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4)
    document.build(
        [
            Table(
                [
                    [
                        "Doc Type",
                        "Document No.",
                        "Date",
                        "Supplier",
                        "Supplier GSTIN",
                        "Taxable Value",
                        "IGST Charged",
                        "CGST Charged",
                        "SGST Charged",
                        "Invoice Value",
                    ],
                    [
                        "Regular",
                        "PTM/0826/220",
                        "02-08-2026",
                        "PrintTech Machines",
                        "29AAACP4203E1ZU",
                        "1,80,000.00",
                        "0.00",
                        "16,200.00",
                        "16,200.00",
                        "2,12,400.00",
                    ],
                ],
                style=TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, "black"),
                        ("FONTSIZE", (0, 0), (-1, -1), 5),
                    ]
                ),
            )
        ]
    )

    parsed = parse_normalized_pdf_tables(
        output.getvalue(),
        document_type="purchase_register",
        source_document_id="document-pdf",
        tax_period="August 2026",
    )

    assert parsed is not None
    assert len(parsed.records) == 1
    assert parsed.records[0].document_number == "PTM/0826/220"
    assert parsed.records[0].taxable_value == Decimal("180000.00")
    assert parsed.records[0].total_tax == Decimal("32400.00")
    assert parsed.records[0].total_document_value == Decimal("212400.00")
    assert parsed.records[0].source_page == 1
