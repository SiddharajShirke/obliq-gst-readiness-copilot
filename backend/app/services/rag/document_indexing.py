"""Idempotent application-document indexing for the Phase 4 assistant."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.config import Settings
from app.repositories.base import DataStore
from app.services.rag.chunking import chunk_document
from app.services.rag.embeddings import embed_texts_async

ELIGIBLE_REVIEW_STATUSES = {"approved", "edited_and_approved"}
EXCLUDED_DOCUMENT_TYPES = {"developer_ground_truth", "unknown"}
EXCLUDED_PROCESSING_STATUSES = {
    "excluded_reference",
    "rejected",
    "processing_failed",
    "failed",
    "upload_failed",
    "needs_assignment",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _record_content(document: dict[str, Any], record: dict[str, Any]) -> str:
    fields = (
        ("Document", document.get("original_name")),
        ("Document type", document.get("document_type")),
        ("Supplier", record.get("supplier_name")),
        ("Supplier GSTIN", record.get("supplier_gstin")),
        ("Customer", record.get("customer_name")),
        ("Customer GSTIN", record.get("customer_gstin")),
        ("Invoice number", record.get("invoice_number")),
        ("Invoice date", record.get("invoice_date")),
        ("Taxable value", record.get("taxable_value")),
        ("IGST", record.get("igst")),
        ("CGST", record.get("cgst")),
        ("SGST/UTGST", record.get("sgst")),
        ("Cess", record.get("cess")),
        ("Total tax", record.get("total_tax")),
        ("Total document value", record.get("invoice_total")),
        ("ITC status", record.get("itc_status")),
        ("RCM", record.get("rcm_flag")),
        ("Transaction type", record.get("transaction_type")),
    )
    return "\n".join(f"{label}: {value}" for label, value in fields if value not in (None, ""))


async def remove_document_chunks(store: DataStore, document_id: str) -> None:
    for row in await store.list_rows("document_chunks", {"document_id": document_id}):
        await store.delete_row("document_chunks", str(row["id"]))


async def _source_chunks(
    store: DataStore,
    settings: Settings,
    document: dict[str, Any],
    extraction: dict[str, Any],
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    records = await store.list_rows(
        "invoice_records", {"document_id": document["id"]}, order="source_row"
    )
    for record in records:
        if record.get("review_status") not in ELIGIBLE_REVIEW_STATUSES:
            continue
        content = _record_content(document, record)
        if not content.strip():
            continue
        source_row = record.get("source_row")
        chunks.append(
            {
                "content": content,
                "page_number": record.get("source_page"),
                "sheet_name": (record.get("source_data") or {}).get("sheet_name"),
                "row_start": source_row,
                "row_end": source_row,
                "section": record.get("invoice_number") or document.get("document_type"),
                "metadata": {
                    "title": document.get("original_name"),
                    "record_id": record.get("id"),
                    "invoice_number": record.get("invoice_number"),
                    "source_type": "application_document",
                },
            }
        )

    raw_text = str(extraction.get("raw_text") or "").strip()
    if raw_text and not records:
        for item in chunk_document(
            raw_text,
            max_chars=settings.rag_chunk_size,
            overlap_chars=settings.rag_chunk_overlap,
        ):
            chunks.append(
                {
                    "content": item.content,
                    "page_number": item.metadata.get("page"),
                    "sheet_name": item.metadata.get("sheet_name"),
                    "row_start": item.metadata.get("row_start"),
                    "row_end": item.metadata.get("row_end"),
                    "section": item.heading,
                    "metadata": {
                        "title": document.get("original_name"),
                        "source_type": "application_document",
                    },
                }
            )
    return chunks


async def index_document(
    store: DataStore,
    settings: Settings,
    document_id: str,
) -> list[dict[str, Any]]:
    document = await store.get_row("documents", document_id)
    if not document:
        return []
    if document.get("document_type") in EXCLUDED_DOCUMENT_TYPES:
        await remove_document_chunks(store, document_id)
        return []
    if document.get("processing_status") in EXCLUDED_PROCESSING_STATUSES:
        await remove_document_chunks(store, document_id)
        return []
    extraction_rows = await store.list_rows(
        "document_extractions", {"document_id": document_id}, limit=1
    )
    if (
        not extraction_rows
        or extraction_rows[0].get("review_status") not in ELIGIBLE_REVIEW_STATUSES
    ):
        await remove_document_chunks(store, document_id)
        return []

    sources = await _source_chunks(store, settings, document, extraction_rows[0])
    if not sources:
        await remove_document_chunks(store, document_id)
        return []
    for source in sources:
        source["checksum"] = hashlib.sha256(source["content"].encode("utf-8")).hexdigest()

    existing = await store.list_rows("document_chunks", {"document_id": document_id})
    existing_ordered = sorted(existing, key=lambda row: int(row.get("chunk_index", 0)))
    if len(existing_ordered) == len(sources) and all(
        row.get("checksum") == source["checksum"]
        and row.get("embedding_model") == settings.embedding_model
        for row, source in zip(existing_ordered, sources, strict=True)
    ):
        return existing_ordered

    await remove_document_chunks(store, document_id)
    vectors = await embed_texts_async(
        [source["content"] for source in sources], settings
    )
    inserted: list[dict[str, Any]] = []
    for index, (source, embedding) in enumerate(zip(sources, vectors, strict=True)):
        inserted.append(
            await store.insert_row(
                "document_chunks",
                {
                    "firm_id": document["firm_id"],
                    "client_id": document["client_id"],
                    "application_id": document["application_id"],
                    "demo_session_id": document.get("demo_session_id"),
                    "document_id": document_id,
                    "document_type": document["document_type"],
                    "chunk_index": index,
                    "content": source["content"],
                    "page_number": source.get("page_number"),
                    "sheet_name": source.get("sheet_name"),
                    "row_start": source.get("row_start"),
                    "row_end": source.get("row_end"),
                    "section": source.get("section"),
                    "metadata": source["metadata"],
                    "checksum": source["checksum"],
                    "embedding": embedding,
                    "embedding_model": settings.embedding_model,
                },
            )
        )
    return inserted


async def sync_application_documents(
    store: DataStore,
    settings: Settings,
    application_id: str,
) -> int:
    documents = await store.list_rows("documents", {"application_id": application_id})
    indexed = 0
    for document in documents:
        chunks = await index_document(store, settings, str(document["id"]))
        indexed += len(chunks)
    return indexed
