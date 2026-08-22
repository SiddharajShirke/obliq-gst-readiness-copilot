"""Cheap deterministic document classification before any LLM fallback."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.document_processing.ingestion import classify_for_ingestion


def classify_document(filename: str, mime_type: str, content: bytes) -> str:
    phase3 = classify_for_ingestion(
        filename=filename,
        mime_type=mime_type,
        content=content,
    )
    if phase3.document_type != "unknown":
        return phase3.document_type
    name = Path(filename).name.lower().replace("-", "_").replace(" ", "_")
    extension = Path(name).suffix.lower()

    if "gstr2b" in name or "gstr_2b" in name or "gstr-2b" in filename.lower():
        return "gstr2b"
    if "sales" in name and "register" in name:
        return "sales_register"
    if ("purchase" in name or "input" in name) and "register" in name:
        return "purchase_register"
    if "sales" in name and "invoice" in name:
        return "sales_invoices"
    if ("purchase" in name or "supplier" in name) and "invoice" in name:
        return "purchase_expense_invoices"

    if extension == ".json" or mime_type == "application/json":
        try:
            data = json.loads(content.decode("utf-8", errors="ignore"))
            keys = {str(key).lower() for key in data.keys()} if isinstance(data, dict) else set()
            if {"gstr2b", "records", "b2b"} & keys:
                return "gstr2b"
        except (json.JSONDecodeError, UnicodeDecodeError):
            return "unknown"

    if extension in {".xlsx", ".xls", ".csv"}:
        if "sale" in name or "outward" in name:
            return "sales_register"
        if "purchase" in name or "inward" in name:
            return "purchase_register"

    return "unknown"
