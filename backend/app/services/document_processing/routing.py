"""Predictable Phase 3 extraction routing with deterministic work first."""

from __future__ import annotations

TABULAR_EXTENSIONS = frozenset({".csv", ".xlsx", ".xls", ".json"})


def choose_extraction_route(
    document_type: str,
    extension: str,
    *,
    has_clean_text: bool,
    vision_capable: bool = False,
) -> str:
    extension = extension.lower()
    if extension in TABULAR_EXTENSIONS:
        return "deterministic"
    if document_type in {"credit_debit_notes", "gst_special_transactions"} and not has_clean_text:
        return "groq"
    if document_type == "unknown":
        return "nvidia"
    if extension in {".png", ".jpg", ".jpeg"} and vision_capable:
        return "nvidia"
    if extension in {".pdf", ".png", ".jpg", ".jpeg", ".docx"}:
        return "nvidia" if has_clean_text else "groq"
    return "deterministic"
