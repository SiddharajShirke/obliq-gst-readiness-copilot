from __future__ import annotations

import pytest

from app.config import Settings
from app.repositories.memory import MemoryStore
from scripts.backfill_application_rag import backfill_application


@pytest.mark.asyncio
async def test_backfill_indexes_only_approved_eligible_documents_idempotently() -> None:
    settings = Settings(app_env="test", ai_mode="mock", use_in_memory_db=True, _env_file=None)
    store = MemoryStore(settings)
    application_id = "new-client-application"
    await store.insert_row(
        "applications",
        {
            "id": application_id,
            "firm_id": "firm-new",
            "client_id": "client-new",
            "period_label": "August 2026",
        },
    )

    async def document(name: str, kind: str, review_status: str, processing: str) -> dict:
        row = await store.insert_row(
            "documents",
            {
                "firm_id": "firm-new",
                "client_id": "client-new",
                "application_id": application_id,
                "original_name": name,
                "document_type": kind,
                "processing_status": processing,
            },
        )
        await store.insert_row(
            "document_extractions",
            {
                "document_id": row["id"],
                "review_status": review_status,
                "raw_text": f"Approved GST evidence from {name}",
            },
        )
        return row

    eligible = await document("Purchase Register.pdf", "purchase_register", "approved", "approved")
    await document("Pending.pdf", "sales_register", "pending", "ready_for_review")
    await document(
        "00_Set_Index_and_Ground_Truth.pdf",
        "developer_ground_truth",
        "approved",
        "excluded_reference",
    )

    first = await backfill_application(store, settings, application_id)
    second = await backfill_application(store, settings, application_id)

    assert first == {"eligible": 1, "indexed_documents": 1, "chunks": 1, "skipped": 2}
    assert second == first
    chunks = await store.list_rows("document_chunks", {"application_id": application_id})
    assert {row["document_id"] for row in chunks} == {eligible["id"]}
    assert all(row["application_id"] == application_id for row in chunks)
