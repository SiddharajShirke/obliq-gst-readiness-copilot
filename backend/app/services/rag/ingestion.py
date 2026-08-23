"""Checksum-based knowledge ingestion into Supabase pgvector or the demo store."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.config import Settings
from app.repositories.base import DataStore
from app.services.rag.chunking import chunk_document
from app.services.rag.embeddings import embed_texts_async
from app.services.rag.extractors import extract_knowledge_bytes


async def ingest_text(
    store: DataStore,
    settings: Settings,
    *,
    text: str,
    title: str,
    source_type: str,
    source_url: str | None,
    firm_id: str | None,
    document_version: str = "demo-v1",
    description: str | None = None,
    storage_path: str | None = None,
    effective_from: str | None = None,
    effective_to: str | None = None,
) -> dict[str, Any]:
    checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
    existing = await store.list_rows(
        "knowledge_sources", {"firm_id": firm_id, "checksum": checksum}, limit=1
    )
    if existing:
        return {
            **existing[0],
            "skipped": True,
            "chunk_count": len(
                await store.list_rows("knowledge_chunks", {"source_id": existing[0]["id"]})
            ),
        }

    source = await store.insert_row(
        "knowledge_sources",
        {
            "firm_id": firm_id,
            "source_type": source_type,
            "title": title,
            "description": description,
            "source_url": source_url,
            "storage_path": storage_path,
            "document_version": document_version,
            "effective_from": effective_from,
            "effective_to": effective_to,
            "checksum": checksum,
            "status": "processing",
        },
    )
    chunks = chunk_document(
        text,
        max_chars=settings.rag_chunk_size,
        overlap_chars=settings.rag_chunk_overlap,
    )
    embeddings = await embed_texts_async(
        [chunk.content for chunk in chunks], settings
    )
    for chunk, embedding in zip(chunks, embeddings, strict=True):
        metadata = {
            "title": title,
            "section": chunk.heading,
            "page": chunk.metadata.get("page"),
            "source_type": source_type,
            "source_url": source_url,
            "effective_from": effective_from,
            "effective_to": effective_to,
            "document_version": document_version,
        }
        await store.insert_row(
            "knowledge_chunks",
            {
                "source_id": source["id"],
                "firm_id": firm_id,
                "chunk_index": chunk.index,
                "content": chunk.content,
                "metadata": metadata,
                "embedding": embedding,
            },
        )
    updated = await store.update_row("knowledge_sources", source["id"], {"status": "active"})
    return {**(updated or source), "skipped": False, "chunk_count": len(chunks)}


async def ingest_bytes(
    store: DataStore,
    settings: Settings,
    *,
    content: bytes,
    filename: str,
    title: str,
    source_type: str,
    source_url: str | None,
    firm_id: str | None,
    document_version: str = "demo-v1",
    description: str | None = None,
    storage_path: str | None = None,
) -> dict[str, Any]:
    extracted = extract_knowledge_bytes(content, filename)
    return await ingest_text(
        store,
        settings,
        text=extracted.text,
        title=title,
        source_type=source_type,
        source_url=source_url,
        firm_id=firm_id,
        document_version=document_version,
        description=description,
        storage_path=storage_path,
    )


async def ingest_file(
    store: DataStore,
    settings: Settings,
    path: Path,
    *,
    title: str | None = None,
    source_type: str = "official_gst",
    source_url: str | None = None,
    firm_id: str | None = None,
    document_version: str = "demo-v1",
) -> dict[str, Any]:
    return await ingest_bytes(
        store,
        settings,
        content=path.read_bytes(),
        filename=path.name,
        title=title or path.stem.replace("_", " ").title(),
        source_type=source_type,
        source_url=source_url,
        firm_id=firm_id,
        document_version=document_version,
    )
