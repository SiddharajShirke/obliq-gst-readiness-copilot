from datetime import date

from app.services.validation import (
    InvoiceInput,
    detect_duplicate_groups,
    validate_gstin_format,
    validate_invoice,
)


def test_validate_gstin_format_accepts_expected_structure() -> None:
    assert validate_gstin_format("27ABCDE1234F1Z5") is True


def test_validate_gstin_format_rejects_bad_value() -> None:
    assert validate_gstin_format("27-INVALID") is False


def test_validate_invoice_flags_arithmetic_and_wrong_period() -> None:
    invoice = InvoiceInput(
        supplier_gstin="27ABCDE1234F1Z5",
        customer_gstin="29ABCDE1234F1Z3",
        invoice_number="INV-100",
        invoice_date=date(2026, 3, 31),
        taxable_value=1000,
        cgst=90,
        sgst=90,
        igst=0,
        cess=0,
        invoice_total=1250,
    )

    findings = validate_invoice(
        invoice,
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        expected_customer_gstin="29ABCDE1234F1Z3",
        today=date(2026, 5, 1),
    )

    assert {finding.finding_type for finding in findings} == {
        "wrong_period",
        "tax_total_mismatch",
    }


def test_detect_duplicate_groups_normalizes_invoice_numbers() -> None:
    records = [
        InvoiceInput(
            supplier_gstin="27ABCDE1234F1Z5",
            invoice_number=" inv-001 ",
            invoice_date=date(2026, 4, 2),
            invoice_total=1180,
        ),
        InvoiceInput(
            supplier_gstin="27ABCDE1234F1Z5",
            invoice_number="INV/001",
            invoice_date=date(2026, 4, 2),
            invoice_total=1180,
        ),
    ]

    groups = detect_duplicate_groups(records)

    assert len(groups) == 1
    assert len(groups[0]) == 2
