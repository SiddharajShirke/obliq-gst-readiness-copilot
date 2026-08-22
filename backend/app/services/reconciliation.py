"""Deterministic exact-field Option A books-to-GSTR-2B reconciliation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

MONEY_FIELDS = ("taxable_value", "igst", "cgst", "sgst", "cess", "total_document_value")
COMPARE_FIELDS = ("invoice_date", *MONEY_FIELDS, "itc_status", "rcm_flag")


def _money(value: Decimal | str | int | None) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _invoice_number(value: str) -> str:
    return value.strip().upper()


@dataclass(slots=True)
class ReconciliationRecord:
    record_id: str
    supplier_gstin: str
    invoice_number: str
    invoice_date: date
    taxable_value: Decimal | None
    cgst: Decimal | None = None
    sgst: Decimal | None = None
    igst: Decimal | None = None
    cess: Decimal | None = None
    total_document_value: Decimal | None = None
    itc_status: str | None = None
    rcm_flag: bool | None = None
    transaction_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in MONEY_FIELDS:
            setattr(self, name, _money(getattr(self, name)))

    @property
    def tax_total(self) -> Decimal | None:
        present = [
            value for value in (self.cgst, self.sgst, self.igst, self.cess) if value is not None
        ]
        return sum(present, Decimal("0")) if present else None

    @property
    def key(self) -> tuple[str, str]:
        return self.supplier_gstin.strip().upper(), _invoice_number(self.invoice_number)

    @property
    def stage_two_key(self) -> tuple[Any, ...]:
        return (
            self.supplier_gstin.strip().upper(),
            self.invoice_date.isoformat(),
            *(getattr(self, name) for name in MONEY_FIELDS),
            self.itc_status.strip().lower() if self.itc_status else None,
            self.rcm_flag,
        )

    def evidence(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "supplier_gstin": self.supplier_gstin.strip().upper(),
            "invoice_number": self.invoice_number.strip(),
            "invoice_date": self.invoice_date.isoformat(),
            **{
                name: str(getattr(self, name)) if getattr(self, name) is not None else None
                for name in MONEY_FIELDS
            },
            "total_tax": str(self.tax_total) if self.tax_total is not None else None,
            "itc_status": self.itc_status,
            "rcm_flag": self.rcm_flag,
            "transaction_type": self.transaction_type,
        }


@dataclass(slots=True)
class ReconciliationItem:
    match_status: str
    purchase_record: ReconciliationRecord | None
    gstr2b_record: ReconciliationRecord | None
    match_score: Decimal
    differences: dict[str, Any] = field(default_factory=dict)
    special_flags: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ReconciliationResult:
    items: list[ReconciliationItem]
    summary: dict[str, int]


def _difference(books: ReconciliationRecord, gstr2b: ReconciliationRecord) -> dict[str, Any]:
    differences: dict[str, Any] = {}
    for field_name in COMPARE_FIELDS:
        left = getattr(books, field_name)
        right = getattr(gstr2b, field_name)
        if isinstance(left, str):
            left = left.strip().lower()
        if isinstance(right, str):
            right = right.strip().lower()
        if left == right:
            continue
        if field_name in MONEY_FIELDS:
            differences[field_name] = {
                "books": str(left) if left is not None else None,
                "gstr2b": str(right) if right is not None else None,
                "difference": (
                    str((left - right).quantize(Decimal("0.01")))
                    if left is not None and right is not None
                    else None
                ),
            }
        else:
            differences[field_name] = {
                "books": left.isoformat() if isinstance(left, date) else left,
                "gstr2b": right.isoformat() if isinstance(right, date) else right,
            }
    return differences


def _flags(books: ReconciliationRecord | None, gstr2b: ReconciliationRecord | None) -> list[str]:
    flags: list[str] = []
    gstr_itc = (gstr2b.itc_status or "").strip().lower() if gstr2b else ""
    if gstr_itc in {"not_available", "not available", "ineligible", "blocked"}:
        flags.append("itc_not_available")
    if any(record and record.rcm_flag is True for record in (books, gstr2b)):
        flags.append("rcm")
    transaction_types = {
        (record.transaction_type or "").strip().lower() for record in (books, gstr2b) if record
    }
    if transaction_types & {"credit_note", "debit_note", "credit note", "debit note"}:
        flags.append("credit_debit_note")
    return flags


def _item(
    status: str,
    books: ReconciliationRecord | None,
    gstr2b: ReconciliationRecord | None,
    *,
    differences: dict[str, Any] | None = None,
    score: str = "0",
    extra_evidence: dict[str, Any] | None = None,
) -> ReconciliationItem:
    evidence = {
        "books": books.evidence() if books else None,
        "gstr2b": gstr2b.evidence() if gstr2b else None,
        "difference_fields": list((differences or {}).keys()),
    }
    evidence.update(extra_evidence or {})
    return ReconciliationItem(
        status,
        books,
        gstr2b,
        Decimal(score),
        differences or {},
        _flags(books, gstr2b),
        evidence,
    )


def reconcile_records(
    purchase_records: list[ReconciliationRecord],
    gstr2b_records: list[ReconciliationRecord],
) -> ReconciliationResult:
    gstr_by_key: dict[tuple[str, str], list[ReconciliationRecord]] = {}
    for record in gstr2b_records:
        gstr_by_key.setdefault(record.key, []).append(record)

    items: list[ReconciliationItem] = []
    consumed_books: set[str] = set()
    consumed_gstr: set[str] = set()
    for books in purchase_records:
        candidates = [
            row for row in gstr_by_key.get(books.key, []) if row.record_id not in consumed_gstr
        ]
        if len(candidates) != 1:
            continue
        gstr = candidates[0]
        differences = _difference(books, gstr)
        items.append(
            _item(
                "value_mismatch" if differences else "exact_match",
                books,
                gstr,
                differences=differences,
                score="0.8" if differences else "1",
            )
        )
        consumed_books.add(books.record_id)
        consumed_gstr.add(gstr.record_id)

    for books in purchase_records:
        if books.record_id in consumed_books:
            continue
        candidates = [
            row
            for row in gstr2b_records
            if row.record_id not in consumed_gstr
            and row.stage_two_key == books.stage_two_key
            and _invoice_number(row.invoice_number) != _invoice_number(books.invoice_number)
        ]
        if len(candidates) == 1:
            gstr = candidates[0]
            differences = {
                "invoice_number": {
                    "books": books.invoice_number.strip(),
                    "gstr2b": gstr.invoice_number.strip(),
                }
            }
            items.append(
                _item(
                    "invoice_number_mismatch",
                    books,
                    gstr,
                    differences=differences,
                    score="0.9",
                )
            )
            consumed_books.add(books.record_id)
            consumed_gstr.add(gstr.record_id)
        elif len(candidates) > 1:
            items.append(
                _item(
                    "ambiguous_match",
                    books,
                    None,
                    extra_evidence={"candidate_record_ids": [row.record_id for row in candidates]},
                )
            )
            consumed_books.add(books.record_id)

    for books in purchase_records:
        if books.record_id not in consumed_books:
            items.append(_item("books_only", books, None))
    for gstr in gstr2b_records:
        if gstr.record_id not in consumed_gstr:
            items.append(_item("gstr2b_only", None, gstr))

    summary = {
        status: sum(item.match_status == status for item in items)
        for status in (
            "exact_match",
            "value_mismatch",
            "invoice_number_mismatch",
            "books_only",
            "gstr2b_only",
            "ambiguous_match",
            "duplicate",
        )
    }
    summary["itc_not_available"] = sum("itc_not_available" in item.special_flags for item in items)
    summary["rcm"] = sum("rcm" in item.special_flags for item in items)
    summary["needs_review"] = sum(
        item.match_status != "exact_match" or bool(item.special_flags) for item in items
    )
    return ReconciliationResult(items, summary)
