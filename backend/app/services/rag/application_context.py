"""Controlled, application-scoped structured facts for the RAG assistant."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

from app.repositories.base import DataStore
from app.services.document_collection import get_document_collection_status
from app.services.validation import normalize_invoice_number


async def get_extraction_summary(store: DataStore, application_id: str) -> dict[str, Any]:
    documents = await store.list_rows("documents", {"application_id": application_id})
    records = await store.list_rows("invoice_records", {"application_id": application_id})
    summaries: dict[str, dict[str, Any]] = {}
    for record in records:
        document_type = str(record.get("document_type") or record.get("source_type") or "unknown")
        target = summaries.setdefault(
            document_type,
            {
                "document_type": document_type,
                "record_count": 0,
                "taxable_value": Decimal("0"),
                "total_tax": Decimal("0"),
                "total_document_value": Decimal("0"),
                "needs_review": 0,
            },
        )
        target["record_count"] += 1
        for source, destination in (
            ("taxable_value", "taxable_value"),
            ("total_tax", "total_tax"),
            ("invoice_total", "total_document_value"),
        ):
            value = record.get(source)
            if value not in (None, ""):
                target[destination] += Decimal(str(value))
        if record.get("review_status") not in {"approved", "edited_and_approved"}:
            target["needs_review"] += 1
    return {
        "document_count": len(
            [
                document
                for document in documents
                if document.get("document_type") != "developer_ground_truth"
            ]
        ),
        "categories": [
            {
                **summary,
                "taxable_value": str(summary["taxable_value"].quantize(Decimal("0.01"))),
                "total_tax": str(summary["total_tax"].quantize(Decimal("0.01"))),
                "total_document_value": str(
                    summary["total_document_value"].quantize(Decimal("0.01"))
                ),
            }
            for summary in summaries.values()
        ],
    }


async def get_transaction_record(
    store: DataStore,
    application_id: str,
    question: str,
) -> list[dict[str, Any]]:
    records = await store.list_rows("invoice_records", {"application_id": application_id})
    normalized_question = normalize_invoice_number(question)
    matched = [
        row
        for row in records
        if row.get("invoice_number")
        and normalize_invoice_number(str(row["invoice_number"])) in normalized_question
    ]
    return matched[:10]


async def get_validation_findings(store: DataStore, application_id: str) -> list[dict[str, Any]]:
    return await store.list_rows(
        "validation_findings", {"application_id": application_id}, order="created_at", desc=True
    )


async def get_reconciliation_summary(store: DataStore, application_id: str) -> dict[str, Any]:
    runs = await store.list_rows(
        "reconciliation_runs",
        {"application_id": application_id},
        order="created_at",
        desc=True,
        limit=1,
    )
    if not runs:
        return {"summary": {}, "items": []}
    items = await store.list_rows(
        "reconciliation_items", {"reconciliation_run_id": runs[0]["id"]}
    )
    return {**runs[0], "items": items}


async def get_reconciliation_overview(
    store: DataStore, application_id: str
) -> dict[str, Any]:
    runs = await store.list_rows(
        "reconciliation_runs",
        {"application_id": application_id},
        order="created_at",
        desc=True,
        limit=1,
    )
    return runs[0] if runs else {"summary": {}}


async def get_reconciliation_item(
    store: DataStore,
    application_id: str,
    question: str,
) -> dict[str, Any] | None:
    reconciliation = await get_reconciliation_summary(store, application_id)
    return find_reconciliation_item(reconciliation, question)


def find_reconciliation_item(
    reconciliation: dict[str, Any], question: str
) -> dict[str, Any] | None:
    normalized_question = normalize_invoice_number(question)
    for item in reconciliation.get("items", []):
        evidence = item.get("evidence") or {}
        invoice_numbers = [
            side.get("invoice_number")
            for side in (evidence.get("books") or {}, evidence.get("gstr2b") or {})
            if isinstance(side, dict)
        ]
        if any(
            value and normalize_invoice_number(str(value)) in normalized_question
            for value in invoice_numbers
        ):
            return item
    return None


async def list_application_alerts(store: DataStore, application_id: str) -> list[dict[str, Any]]:
    return await store.list_rows(
        "alerts", {"application_id": application_id}, order="created_at", desc=True
    )


def draft_missing_document_reminder(
    collection: dict[str, Any], client_name: str, period: str
) -> str:
    missing = [
        row["label"]
        for row in collection.get("requirements", [])
        if row["status"] != "received"
    ]
    if not missing:
        return "All required document categories have been received. No reminder is needed."
    bullets = "\n".join(f"• {label}" for label in missing)
    return (
        f"Hello {client_name},\n\nThe following documents are still pending for {period}:\n\n"
        f"{bullets}\n\nPlease upload them using your existing secure upload link.\n\nThank you."
    )


async def load_structured_facts(
    store: DataStore,
    *,
    application_id: str,
    question: str,
    intent: str,
    application: dict[str, Any] | None = None,
) -> dict[str, Any]:
    application = application or await store.get_row("applications", application_id)
    if not application:
        return {"error": "Application not found"}
    client, collection = await asyncio.gather(
        store.get_row("clients", application["client_id"]),
        get_document_collection_status(store, application_id),
    )
    facts: dict[str, Any] = {
        "application": {
            key: application.get(key)
            for key in (
                "id", "client_id", "demo_session_id", "period_label", "period_start",
                "period_end", "financial_year", "filing_frequency", "status",
            )
        },
        "client": {
            key: (client or {}).get(key)
            for key in ("id", "business_name", "legal_name", "gstin", "state", "business_type")
        },
        "collection": collection,
    }
    pending: dict[str, Any] = {}
    if intent in {"extraction_summary", "guidance"}:
        pending["extraction_summary"] = get_extraction_summary(store, application_id)
    if intent in {"transaction_lookup", "reconciliation", "alert_explanation"}:
        pending["transactions"] = get_transaction_record(store, application_id, question)
    if intent in {"validation", "guidance"}:
        pending["validation_findings"] = get_validation_findings(store, application_id)
    if intent in {"reconciliation", "alerts", "alert_explanation"}:
        pending["reconciliation"] = get_reconciliation_summary(store, application_id)
    elif intent == "guidance":
        pending["reconciliation"] = get_reconciliation_overview(store, application_id)
    if intent in {"alerts", "guidance", "alert_explanation"}:
        pending["alerts"] = list_application_alerts(store, application_id)
    if pending:
        values = await asyncio.gather(*pending.values())
        facts.update(dict(zip(pending, values, strict=True)))
    if "reconciliation" in facts:
        facts["reconciliation_item"] = find_reconciliation_item(
            facts["reconciliation"], question
        )
    if intent == "draft_reminder":
        facts["draft_reminder"] = draft_missing_document_reminder(
            collection,
            str((client or {}).get("business_name") or "Client"),
            str(application.get("period_label") or "the GST period"),
        )
    return facts
