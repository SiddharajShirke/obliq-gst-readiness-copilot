"""Purchase-register to GSTR-2B reconciliation logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.services.validation import normalize_invoice_number


@dataclass(slots=True)
class ReconciliationRecord:
    record_id: str
    supplier_gstin: str
    invoice_number: str
    invoice_date: date
    taxable_value: Decimal
    cgst: Decimal = Decimal("0")
    sgst: Decimal = Decimal("0")
    igst: Decimal = Decimal("0")
    cess: Decimal = Decimal("0")
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def tax_total(self) -> Decimal:
        return self.cgst + self.sgst + self.igst + self.cess

    @property
    def key(self) -> tuple[str, str]:
        return self.supplier_gstin.strip().upper(), normalize_invoice_number(self.invoice_number)


@dataclass(slots=True)
class ReconciliationItem:
    match_status: str
    purchase_record: ReconciliationRecord | None
    gstr2b_record: ReconciliationRecord | None
    match_score: float
    differences: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ReconciliationResult:
    items: list[ReconciliationItem]
    summary: dict[str, int]


def _money_diff(a: Decimal, b: Decimal) -> str:
    return str((a - b).quantize(Decimal("0.01")))


def reconcile_records(
    purchase_records: list[ReconciliationRecord],
    gstr2b_records: list[ReconciliationRecord],
    *,
    amount_tolerance: Decimal = Decimal("1.00"),
) -> ReconciliationResult:
    gstr_index: dict[tuple[str, str], list[ReconciliationRecord]] = {}
    for record in gstr2b_records:
        gstr_index.setdefault(record.key, []).append(record)

    items: list[ReconciliationItem] = []
    consumed: set[str] = set()

    for purchase in purchase_records:
        candidates = [item for item in gstr_index.get(purchase.key, []) if item.record_id not in consumed]
        if not candidates:
            items.append(ReconciliationItem("purchase_only", purchase, None, 0.0))
            continue

        candidate = min(
            candidates,
            key=lambda item: abs(item.taxable_value - purchase.taxable_value)
            + abs(item.tax_total - purchase.tax_total),
        )
        consumed.add(candidate.record_id)
        differences: dict[str, Any] = {}

        if candidate.invoice_date != purchase.invoice_date:
            differences["invoice_date"] = {
                "purchase": purchase.invoice_date.isoformat(),
                "gstr2b": candidate.invoice_date.isoformat(),
            }
        if abs(candidate.taxable_value - purchase.taxable_value) > amount_tolerance:
            differences["taxable_value"] = _money_diff(purchase.taxable_value, candidate.taxable_value)
        if abs(candidate.tax_total - purchase.tax_total) > amount_tolerance:
            differences["tax_total"] = _money_diff(purchase.tax_total, candidate.tax_total)

        if "invoice_date" in differences:
            status = "date_mismatch"
            score = 0.75
        elif differences:
            status = "amount_mismatch"
            score = 0.8
        else:
            status = "matched"
            score = 1.0

        items.append(ReconciliationItem(status, purchase, candidate, score, differences))

    for record in gstr2b_records:
        if record.record_id not in consumed:
            items.append(ReconciliationItem("gstr2b_only", None, record, 0.0))

    summary = {
        key: sum(item.match_status == key for item in items)
        for key in (
            "matched",
            "purchase_only",
            "gstr2b_only",
            "amount_mismatch",
            "date_mismatch",
            "possible_duplicate",
        )
    }
    return ReconciliationResult(items=items, summary=summary)
