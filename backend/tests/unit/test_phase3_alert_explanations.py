from unittest.mock import AsyncMock

import pytest

from app.config import Settings
from app.services.alert_explanations import (
    build_alert_evidence,
    generate_alert_explanation,
)

EVIDENCE = {
    "books": {
        "invoice_number": "EFI/0826/889",
        "supplier_gstin": "27ABCDE1234F1Z5",
        "taxable_value": "90000.00",
    },
    "gstr2b": {
        "invoice_number": "EFI/0826/889",
        "supplier_gstin": "27ABCDE1234F1Z5",
        "taxable_value": "95000.00",
    },
    "difference_fields": ["taxable_value"],
}


def test_alert_evidence_is_deterministic_and_contains_no_ground_truth() -> None:
    payload = build_alert_evidence(
        alert_type="TAXABLE_VALUE_MISMATCH",
        client_name="Kaveri Office Systems LLP",
        tax_period="August 2026",
        reconciliation_evidence=EVIDENCE,
    )
    assert payload["alert_type"] == "TAXABLE_VALUE_MISMATCH"
    assert payload["books"]["taxable_value"] == "90000.00"
    assert "ground_truth" not in str(payload).lower()


@pytest.mark.asyncio
async def test_alert_explanation_uses_nvidia_first() -> None:
    nvidia = AsyncMock(
        return_value={
            "title": "Taxable Value Mismatch",
            "what_happened": "Books show ₹90,000 and GSTR-2B shows ₹95,000.",
            "why_flagged": "The exact values differ by ₹5,000.",
            "what_ca_should_review": "Compare the source invoice and both records.",
            "short_summary": "₹5,000 difference requires CA review.",
        }
    )
    groq = AsyncMock()
    settings = Settings(app_env="test", whatsapp_provider="mock", ai_mode="mock")
    result = await generate_alert_explanation(
        settings,
        EVIDENCE,
        nvidia_complete=nvidia,
        groq_complete=groq,
    )
    assert result.provider == "nvidia"
    assert result.explanation.short_summary.startswith("₹5,000")
    nvidia.assert_awaited_once()
    groq.assert_not_awaited()


@pytest.mark.asyncio
async def test_alert_explanation_falls_back_to_groq_after_nvidia_failure() -> None:
    nvidia = AsyncMock(side_effect=RuntimeError("provider unavailable"))
    groq = AsyncMock(
        return_value={
            "title": "Taxable Value Mismatch",
            "what_happened": "The exact compared values differ.",
            "why_flagged": "Deterministic reconciliation found a mismatch.",
            "what_ca_should_review": "Review the source records.",
            "short_summary": "CA review is required.",
        }
    )
    settings = Settings(app_env="test", whatsapp_provider="mock", ai_mode="mock")
    result = await generate_alert_explanation(
        settings,
        EVIDENCE,
        nvidia_complete=nvidia,
        groq_complete=groq,
    )
    assert result.provider == "groq"
    assert result.fallback_reason == "RuntimeError"
    groq.assert_awaited_once()
