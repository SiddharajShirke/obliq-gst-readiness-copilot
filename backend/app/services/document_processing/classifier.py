"""Cheap deterministic document classification before any LLM fallback."""

from __future__ import annotations

import json
from pathlib import Path


def classify_document(filename: str, mime_type: str, content: bytes) -> str:
    name = Path(filename).name.lower().replace("-", "_").replace(" ", "_")
    extension = Path(name).suffix.lower()

    if "gstr2b" in name or "gstr_2b" in name or "gstr-2b" in filename.lower():
        return "gstr2b"
    if "sales" in name and "register" in name:
        return "sales_register"
    if ("purchase" in name or "input" in name) and "register" in name:
        return "purchase_register"
    if "sales" in name and "invoice" in name:
        return "sales_invoice"
    if ("purchase" in name or "supplier" in name) and "invoice" in name:
        return "purchase_invoice"

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

    if extension in {".pdf", ".png", ".jpg", ".jpeg"}:
        return "purchase_invoice"
    return "unknown"
