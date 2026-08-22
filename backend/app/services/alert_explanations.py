"""Read-only AI assistance for explicitly raised reconciliation alerts."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.prompts.alert_explanations import ALERT_EXPLANATION_SYSTEM_PROMPT
from app.schemas.alerts import AlertExplanation
from app.services.llm.providers import complete_groq_json, complete_nvidia_json

AIComplete = Callable[..., Awaitable[dict[str, Any]]]
ALLOWED_EVIDENCE_FIELDS = {
    "record_id",
    "supplier_gstin",
    "invoice_number",
    "invoice_date",
    "taxable_value",
    "igst",
    "cgst",
    "sgst",
    "cess",
    "total_document_value",
    "total_tax",
    "itc_status",
    "rcm_flag",
    "transaction_type",
}


@dataclass(frozen=True, slots=True)
class GeneratedAlertExplanation:
    explanation: AlertExplanation
    provider: str
    model: str
    fallback_reason: str | None = None


def _safe_side(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {key: value.get(key) for key in ALLOWED_EVIDENCE_FIELDS if key in value}


def build_alert_evidence(
    *,
    alert_type: str,
    client_name: str,
    tax_period: str,
    reconciliation_evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "alert_type": alert_type,
        "client_name": client_name,
        "tax_period": tax_period,
        "books": _safe_side(reconciliation_evidence.get("books")),
        "gstr2b": _safe_side(reconciliation_evidence.get("gstr2b")),
        "difference_fields": [
            str(field) for field in reconciliation_evidence.get("difference_fields", [])
        ],
    }


async def generate_alert_explanation(
    settings: Settings,
    evidence: dict[str, Any],
    *,
    nvidia_complete: AIComplete = complete_nvidia_json,
    groq_complete: AIComplete = complete_groq_json,
) -> GeneratedAlertExplanation:
    user_prompt = "Explain this immutable deterministic evidence:\n" + json.dumps(
        evidence, separators=(",", ":"), ensure_ascii=False
    )
    try:
        output = await nvidia_complete(
            settings,
            system_prompt=ALERT_EXPLANATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        return GeneratedAlertExplanation(
            AlertExplanation.model_validate(output),
            "nvidia",
            settings.nvidia_small_model or "mock-nvidia",
        )
    except Exception as nvidia_error:
        output = await groq_complete(
            settings,
            system_prompt=ALERT_EXPLANATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        return GeneratedAlertExplanation(
            AlertExplanation.model_validate(output),
            "groq",
            settings.effective_groq_model,
            type(nvidia_error).__name__,
        )
