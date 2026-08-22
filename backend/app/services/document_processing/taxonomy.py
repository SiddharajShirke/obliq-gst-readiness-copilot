"""Canonical Phase 3 GST document taxonomy and deterministic filename routing."""

from __future__ import annotations

import re
from pathlib import Path

CLIENT_REQUIREMENTS: dict[str, str] = {
    "sales_register": "Sales Register",
    "purchase_register": "Purchase Register",
    "sales_invoices": "Sales Invoices",
    "purchase_expense_invoices": "Purchase & Expense Invoices",
    "credit_debit_notes": "Credit & Debit Notes",
    "gst_special_transactions": "GST Special Transactions",
}

BUSINESS_DOCUMENT_TYPES = frozenset((*CLIENT_REQUIREMENTS, "gstr2b"))
ALL_DOCUMENT_TYPES = frozenset((*BUSINESS_DOCUMENT_TYPES, "developer_ground_truth", "unknown"))


def _normalized_name(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).stem.lower()
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_")


def classify_known_filename(filename: str) -> str | None:
    """Recognize the synthetic package without reading expected-answer content."""

    name = _normalized_name(filename)
    if "ground_truth" in name or "set_index" in name:
        return "developer_ground_truth"
    if "gstr_2b" in name or "gstr2b" in name:
        return "gstr2b"
    if "purchase" in name and "expense" in name and "invoice" in name:
        return "purchase_expense_invoices"
    if "credit" in name and "debit" in name and "note" in name:
        return "credit_debit_notes"
    if "gst" in name and "special" in name and "transaction" in name:
        return "gst_special_transactions"
    if "sales" in name and "register" in name:
        return "sales_register"
    if "purchase" in name and "register" in name:
        return "purchase_register"
    if "sales" in name and "invoice" in name:
        return "sales_invoices"
    return None
