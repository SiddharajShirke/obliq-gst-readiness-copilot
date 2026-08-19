"""Deterministic GST invoice validation for the prototype."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def _decimal(value: Decimal | int | float | str | None) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def normalize_invoice_number(value: str | None) -> str:
    """Normalize invoice numbers for duplicate and reconciliation matching."""
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def validate_gstin_format(value: str | None) -> bool:
    """Perform a format-only GSTIN check; this does not verify registration status."""
    return bool(value and GSTIN_PATTERN.fullmatch(value.strip().upper()))


@dataclass(slots=True)
class InvoiceInput:
    supplier_name: str | None = None
    supplier_gstin: str | None = None
    customer_name: str | None = None
    customer_gstin: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    taxable_value: Decimal | int | float | str | None = Decimal("0")
    cgst: Decimal | int | float | str | None = Decimal("0")
    sgst: Decimal | int | float | str | None = Decimal("0")
    igst: Decimal | int | float | str | None = Decimal("0")
    cess: Decimal | int | float | str | None = Decimal("0")
    invoice_total: Decimal | int | float | str | None = Decimal("0")
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ValidationFinding:
    finding_type: str
    severity: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def validate_invoice(
    invoice: InvoiceInput,
    *,
    period_start: date,
    period_end: date,
    expected_customer_gstin: str | None = None,
    today: date | None = None,
    arithmetic_tolerance: Decimal = Decimal("1.00"),
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    today = today or date.today()

    if not invoice.invoice_number:
        findings.append(
            ValidationFinding("missing_required_field", "high", "Invoice number is missing.")
        )

    if invoice.supplier_gstin and not validate_gstin_format(invoice.supplier_gstin):
        findings.append(
            ValidationFinding(
                "invalid_gstin_format",
                "medium",
                "Supplier GSTIN does not match the expected format.",
                {"value": invoice.supplier_gstin},
            )
        )
    elif not invoice.supplier_gstin:
        findings.append(ValidationFinding("missing_gstin", "medium", "Supplier GSTIN is missing."))

    if invoice.invoice_date is None:
        findings.append(ValidationFinding("invalid_date", "high", "Invoice date is missing."))
    else:
        if invoice.invoice_date > today:
            findings.append(
                ValidationFinding("future_date", "high", "Invoice date is in the future.")
            )
        if not period_start <= invoice.invoice_date <= period_end:
            findings.append(
                ValidationFinding(
                    "wrong_period",
                    "medium",
                    "Invoice does not belong to the selected GST period.",
                    {
                        "invoice_date": invoice.invoice_date.isoformat(),
                        "period_start": period_start.isoformat(),
                        "period_end": period_end.isoformat(),
                    },
                )
            )

    if expected_customer_gstin and invoice.customer_gstin:
        if invoice.customer_gstin.strip().upper() != expected_customer_gstin.strip().upper():
            findings.append(
                ValidationFinding(
                    "wrong_client",
                    "high",
                    "Customer GSTIN does not match the selected client.",
                    {
                        "document_gstin": invoice.customer_gstin,
                        "client_gstin": expected_customer_gstin,
                    },
                )
            )

    expected_total = sum(
        (
            _decimal(invoice.taxable_value),
            _decimal(invoice.cgst),
            _decimal(invoice.sgst),
            _decimal(invoice.igst),
            _decimal(invoice.cess),
        ),
        Decimal("0"),
    )
    actual_total = _decimal(invoice.invoice_total)
    if abs(expected_total - actual_total) > arithmetic_tolerance:
        findings.append(
            ValidationFinding(
                "tax_total_mismatch",
                "high",
                "Invoice total does not match taxable value plus tax components.",
                {
                    "calculated_total": str(expected_total),
                    "invoice_total": str(actual_total),
                    "difference": str(actual_total - expected_total),
                },
            )
        )

    return findings


def duplicate_key(invoice: InvoiceInput) -> tuple[str, str, str, str]:
    return (
        (invoice.supplier_gstin or "").strip().upper(),
        normalize_invoice_number(invoice.invoice_number),
        invoice.invoice_date.isoformat() if invoice.invoice_date else "",
        str(_decimal(invoice.invoice_total).quantize(Decimal("0.01"))),
    )


def detect_duplicate_groups(records: list[InvoiceInput]) -> list[list[InvoiceInput]]:
    grouped: dict[tuple[str, str, str, str], list[InvoiceInput]] = {}
    for record in records:
        key = duplicate_key(record)
        grouped.setdefault(key, []).append(record)
    return [group for key, group in grouped.items() if all(key) and len(group) > 1]
