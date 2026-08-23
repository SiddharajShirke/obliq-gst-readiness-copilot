"""Idempotently index retained, approved application documents for Phase 4 RAG."""

from __future__ import annotations

import argparse
import asyncio

from app.config import Settings, get_settings
from app.repositories import get_store
from app.repositories.base import DataStore
from app.services.rag.document_indexing import (
    ELIGIBLE_REVIEW_STATUSES,
    EXCLUDED_DOCUMENT_TYPES,
    EXCLUDED_PROCESSING_STATUSES,
    index_document,
)


async def backfill_application(
    store: DataStore,
    settings: Settings,
    application_id: str,
) -> dict[str, int]:
    documents = await store.list_rows("documents", {"application_id": application_id})
    eligible = 0
    indexed_documents = 0
    chunks = 0
    for document in documents:
        extractions = await store.list_rows(
            "document_extractions", {"document_id": document["id"]}, limit=1
        )
        usable = bool(
            document.get("document_type") not in EXCLUDED_DOCUMENT_TYPES
            and document.get("processing_status") not in EXCLUDED_PROCESSING_STATUSES
            and extractions
            and extractions[0].get("review_status") in ELIGIBLE_REVIEW_STATUSES
        )
        if not usable:
            continue
        eligible += 1
        indexed = await index_document(store, settings, str(document["id"]))
        if indexed:
            indexed_documents += 1
            chunks += len(indexed)
    return {
        "eligible": eligible,
        "indexed_documents": indexed_documents,
        "chunks": chunks,
        "skipped": len(documents) - eligible,
    }


async def _run(application_id: str | None, all_applications: bool) -> None:
    settings = get_settings()
    store = get_store()
    if all_applications:
        application_ids = [str(row["id"]) for row in await store.list_rows("applications")]
    elif application_id:
        application_ids = [application_id]
    else:
        raise ValueError("Provide --application-id or --all")
    totals = {
        "applications": 0,
        "eligible": 0,
        "indexed_documents": 0,
        "chunks": 0,
        "skipped": 0,
    }
    for target in application_ids:
        result = await backfill_application(store, settings, target)
        totals["applications"] += 1
        for key, value in result.items():
            totals[key] += value
    print(
        "RAG backfill complete: "
        + " ".join(f"{key}={value}" for key, value in totals.items())
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--application-id")
    target.add_argument("--all", action="store_true")
    args = parser.parse_args()
    asyncio.run(_run(args.application_id, args.all))


if __name__ == "__main__":
    main()
