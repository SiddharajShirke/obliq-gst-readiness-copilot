"""Read-only correction proposals with explicit CA-controlled application."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.config import Settings
from app.repositories.base import DataStore
from app.services.llm.providers import complete_groq_json, complete_nvidia_json

ALLOWED_CORRECTION_FIELDS = frozenset(
    {
        "invoice_number",
        "invoice_date",
        "supplier_name",
        "supplier_gstin",
        "customer_name",
        "customer_gstin",
        "taxable_value",
        "gst_rate",
        "igst",
        "cgst",
        "sgst",
        "cess",
        "total_tax",
        "invoice_total",
        "itc_status",
        "rcm_flag",
        "transaction_type",
        "place_of_supply",
        "hsn_sac",
    }
)


class SuggestedChange(BaseModel):
    record_id: str
    field: str
    proposed_value: Any = None
    rationale: str = Field(default="CA review requested", max_length=1000)


class SuggestedChanges(BaseModel):
    changes: list[SuggestedChange] = Field(default_factory=list, max_length=500)
    rationale: str = Field(
        default="Review the proposed values against source evidence", max_length=2000
    )


def _validate_records(
    records: list[dict[str, Any] | None], application_id: str, firm_id: str
) -> list[dict[str, Any]]:
    if any(
        row is None
        or str(row.get("application_id")) != str(application_id)
        or str(row.get("firm_id")) != str(firm_id)
        or row.get("review_status") not in {"approved", "edited_and_approved"}
        for row in records
    ):
        raise LookupError("One or more approved records were not found")
    return [row for row in records if row is not None]


def _materialize_changes(
    records: list[dict[str, Any]], suggestions: list[SuggestedChange]
) -> list[dict[str, Any]]:
    by_id = {str(row["id"]): row for row in records}
    changes: list[dict[str, Any]] = []
    for suggestion in suggestions:
        if suggestion.field not in ALLOWED_CORRECTION_FIELDS:
            raise ValueError(f"Unsupported correction field: {suggestion.field}")
        record = by_id.get(str(suggestion.record_id))
        if not record:
            raise ValueError("Correction targets a record outside the selected application")
        changes.append(
            {
                "record_id": record["id"],
                "field": suggestion.field,
                "before": record.get(suggestion.field),
                "after": suggestion.proposed_value,
                "rationale": suggestion.rationale,
            }
        )
    return changes


def _review_guidance(findings: list[dict[str, Any]]) -> str:
    guidance: list[str] = []
    for finding in findings:
        details = finding.get("details") or {}
        if finding.get("finding_type") == "wrong_period":
            guidance.append(
                f"Invoice date {details.get('invoice_date') or 'unknown'} is outside the selected "
                f"GST period {details.get('period_start') or 'unknown'} to "
                f"{details.get('period_end') or 'unknown'}. Verify the original document: if the "
                "date is accurate, keep the value and assign the transaction to the correct "
                "period; "
                "if extraction is wrong, correct invoice_date using the source document."
            )
        elif finding.get("finding_type") == "tax_arithmetic_mismatch":
            guidance.append(
                "Verify the component taxes and taxable value against the source invoice before "
                "changing the recorded total tax."
            )
        else:
            guidance.append(
                f"Review {finding.get('message') or finding.get('finding_type') or 'the finding'} "
                "against the original source before changing any extracted field."
            )
    return " ".join(guidance)[:2000] or (
        "No selected finding contains enough source evidence for a safe correction. "
        "Verify the original document before changing the extracted value."
    )


async def create_correction_proposal(
    store: DataStore,
    settings: Settings,
    *,
    application: dict[str, Any],
    user_id: str,
    record_ids: list[str],
    finding_ids: list[str],
    mode: str,
    manual_changes: dict[str, Any],
    rationale: str | None,
) -> dict[str, Any]:
    raw_records = [await store.get_row("invoice_records", record_id) for record_id in record_ids]
    records = _validate_records(raw_records, application["id"], application["firm_id"])
    raw_findings = [
        await store.get_row("validation_findings", finding_id)
        for finding_id in finding_ids
    ]
    if any(
        finding is None
        or str(finding.get("application_id")) != str(application["id"])
        or str(finding.get("firm_id")) != str(application["firm_id"])
        or (
            finding.get("invoice_record_id")
            and str(finding.get("invoice_record_id")) not in {str(row["id"]) for row in records}
        )
        for finding in raw_findings
    ):
        raise LookupError("One or more validation findings were not found")
    findings = [finding for finding in raw_findings if finding is not None]
    provider = None
    model = None
    if mode == "manual":
        suggestions = [
            SuggestedChange(
                record_id=str(record["id"]),
                field=field,
                proposed_value=value,
                rationale=rationale or "Manual correction proposed by the CA",
            )
            for record in records
            for field, value in manual_changes.items()
        ]
        proposal_rationale = rationale or "Manual correction requires explicit confirmation"
    else:
        evidence = {
            "application": {
                "period_label": application.get("period_label"),
                "period_start": application.get("period_start"),
                "period_end": application.get("period_end"),
            },
            "records": [
                {key: row.get(key) for key in ("id", *sorted(ALLOWED_CORRECTION_FIELDS))}
                for row in records
            ],
            "deterministic_findings": [
                {
                    "id": finding.get("id"),
                    "finding_type": finding.get("finding_type"),
                    "message": finding.get("message"),
                    "details": finding.get("details") or {},
                }
                for finding in findings
            ],
        }
        deterministic_guidance = _review_guidance(findings)
        if settings.ai_mode == "mock":
            generated = {
                "changes": [],
                "rationale": deterministic_guidance,
            }
            provider, model = "nvidia", settings.nvidia_small_model or "mock-nvidia-small"
        else:
            system_prompt = (
                "You assist a CA by proposing corrections only. Return JSON with changes: "
                "[{record_id, field, proposed_value, rationale}] and rationale. Do not change IDs, "
                "decide GST/ITC treatment, or add unsupported facts."
            )
            user_prompt = "Review only this approved evidence:\n" + json.dumps(
                evidence, default=str
            )
            try:
                generated = await complete_nvidia_json(
                    settings, system_prompt=system_prompt, user_prompt=user_prompt
                )
                provider, model = "nvidia", settings.nvidia_small_model
            except Exception:
                generated = await complete_groq_json(
                    settings, system_prompt=system_prompt, user_prompt=user_prompt
                )
                provider, model = "groq", settings.effective_groq_model
        validated = SuggestedChanges.model_validate(generated)
        suggestions = validated.changes
        proposal_rationale = validated.rationale
        if not suggestions and deterministic_guidance not in proposal_rationale:
            proposal_rationale = f"{proposal_rationale} {deterministic_guidance}"[:2000]
    changes = _materialize_changes(records, suggestions)
    now = datetime.now(UTC).isoformat()
    return await store.insert_row(
        "validation_correction_proposals",
        {
            "firm_id": application["firm_id"],
            "client_id": application["client_id"],
            "application_id": application["id"],
            "proposal_type": mode,
            "status": "proposed",
            "record_ids": [row["id"] for row in records],
            "changes": changes,
            "rationale": proposal_rationale,
            "provider": provider,
            "model": model,
            "proposed_by": user_id,
            "proposed_at": now,
        },
    )


async def apply_correction_proposal(
    store: DataStore, proposal: dict[str, Any], *, user_id: str
) -> dict[str, Any]:
    if proposal.get("status") != "proposed":
        raise ValueError("Correction proposal has already been decided")
    for change in proposal.get("changes") or []:
        record = await store.get_row("invoice_records", change["record_id"])
        if not record or str(record.get("application_id")) != str(proposal["application_id"]):
            raise LookupError("Correction record is no longer available")
        await store.update_row(
            "invoice_records",
            record["id"],
            {change["field"]: change.get("after"), "review_status": "edited_and_approved"},
        )
    updated = await store.update_row(
        "validation_correction_proposals",
        proposal["id"],
        {
            "status": "applied",
            "decided_by": user_id,
            "decided_at": datetime.now(UTC).isoformat(),
        },
    )
    assert updated is not None
    return updated
