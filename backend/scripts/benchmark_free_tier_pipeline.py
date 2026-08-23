"""Benchmark the real Phase 3/4 pipeline against synthetic GST document sets.

The benchmark intentionally uses the in-memory repository so it cannot pollute a
hosted Supabase project. It still executes the production document parser, live
NVIDIA/Groq routing, normalization, CA-approval indexing path, local embedding
model, LangGraph assistant, and application-scope guards.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agents.rag_assistant import RAGAssistant
from app.config import Settings
from app.repositories.memory import DEMO_ADMIN_ID, DEMO_FIRM_ID, MemoryStore
from app.services.document_processing.parsers import read_pdf_text
from app.services.document_processing.pipeline import (
    ingest_document,
    submit_ingested_documents,
)
from app.services.document_processing.processor import DocumentProcessor
from app.services.document_processing.taxonomy import CLIENT_REQUIREMENTS
from app.services.rag.document_indexing import index_document
from app.services.rag.retrieval import retrieve_application_documents
from app.services.secure_upload import ResolvedUploadContext

GROUND_TRUTH_MARKERS = ("ground_truth", "set_index")


@dataclass(frozen=True, slots=True)
class DatasetSet:
    name: str
    directory: Path
    business_files: tuple[Path, ...]
    excluded_references: tuple[Path, ...]


def discover_dataset_sets(dataset_root: Path) -> list[DatasetSet]:
    """Return deterministic dataset groups without reading Ground Truth content."""

    if not dataset_root.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_root}")
    discovered: list[DatasetSet] = []
    for directory in sorted(path for path in dataset_root.iterdir() if path.is_dir()):
        files = tuple(sorted(path for path in directory.iterdir() if path.is_file()))
        excluded = tuple(
            path
            for path in files
            if any(marker in path.stem.lower() for marker in GROUND_TRUTH_MARKERS)
        )
        business = tuple(path for path in files if path not in excluded)
        if business:
            discovered.append(
                DatasetSet(
                    name=directory.name,
                    directory=directory,
                    business_files=business,
                    excluded_references=excluded,
                )
            )
    return discovered


def _period_for_set(name: str) -> tuple[str, str, str]:
    normalized = name.lower()
    if "july_2026" in normalized:
        return "July 2026", "2026-07-01", "2026-07-31"
    if "august_2026" in normalized:
        return "August 2026", "2026-08-01", "2026-08-31"
    if "september_2026" in normalized:
        return "September 2026", "2026-09-01", "2026-09-30"
    raise ValueError(f"Cannot derive GST period from dataset directory: {name}")


async def _context_for_set(store: MemoryStore, dataset: DatasetSet) -> ResolvedUploadContext:
    period_label, period_start, period_end = _period_for_set(dataset.name)
    client = await store.get_row("clients", "20000000-0000-0000-0000-000000000001")
    application = await store.get_row("applications", "30000000-0000-0000-0000-000000000001")
    firm = await store.get_row("firms", DEMO_FIRM_ID)
    if not client or not application or not firm:
        raise RuntimeError("Benchmark fixture workspace could not be initialized")
    application = (
        await store.update_row(
            "applications",
            application["id"],
            {
                "period_label": period_label,
                "period_start": period_start,
                "period_end": period_end,
                "financial_year": "2026-27",
                "status": "document_collection",
            },
        )
        or application
    )
    checklist = await store.list_rows(
        "document_requirements", {"application_id": application["id"]}
    )
    link = await store.insert_row(
        "upload_links",
        {
            "firm_id": firm["id"],
            "client_id": client["id"],
            "application_id": application["id"],
            "demo_session_id": None,
            "requirement_id": None,
            "token_hash": f"benchmark-{uuid.uuid4()}",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "revoked_at": None,
        },
    )
    return ResolvedUploadContext(
        link=link,
        firm=firm,
        client=client,
        application=application,
        demo_session=None,
        checklist=checklist,
    )


async def _approve_and_index(
    store: MemoryStore, settings: Settings, document: dict[str, Any]
) -> tuple[int, float]:
    if document.get("document_type") not in CLIENT_REQUIREMENTS:
        return 0, 0.0
    records = await store.list_rows("invoice_records", {"document_id": document["id"]})
    for record in records:
        await store.update_row(
            "invoice_records",
            record["id"],
            {
                "review_status": "approved",
                "reviewed_by": DEMO_ADMIN_ID,
                "reviewed_at": datetime.now(UTC).isoformat(),
            },
        )
    extractions = await store.list_rows(
        "document_extractions", {"document_id": document["id"]}, limit=1
    )
    if extractions:
        await store.update_row(
            "document_extractions",
            extractions[0]["id"],
            {
                "review_status": "approved",
                "reviewed_by": DEMO_ADMIN_ID,
                "reviewed_at": datetime.now(UTC).isoformat(),
            },
        )
    await store.update_row("documents", document["id"], {"processing_status": "approved"})
    started = time.perf_counter()
    chunks = await index_document(store, settings, str(document["id"]))
    return len(chunks), time.perf_counter() - started


async def benchmark_set(dataset: DatasetSet, base_settings: Settings) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix="obliq-benchmark-", ignore_cleanup_errors=True
    ) as runtime:
        runtime_path = Path(runtime)
        settings = base_settings.model_copy(
            update={
                "app_env": "benchmark",
                "demo_mode": True,
                "use_in_memory_db": True,
                "ai_mode": "live",
                "heavy_processing_concurrency": 1,
                "local_upload_dir": runtime_path / "uploads",
                "local_export_dir": runtime_path / "exports",
            }
        )
        store = MemoryStore(settings)
        context = await _context_for_set(store, dataset)

        upload_started = time.perf_counter()
        uploaded: list[dict[str, Any]] = []
        input_profile: list[dict[str, Any]] = []
        for path in dataset.business_files:
            content = path.read_bytes()
            direct_text = read_pdf_text(content) if path.suffix.lower() == ".pdf" else ""
            input_profile.append(
                {
                    "file": path.name,
                    "bytes": len(content),
                    "direct_text_chars": len(direct_text),
                    "ocr_required": path.suffix.lower() == ".pdf" and not direct_text.strip(),
                }
            )
            uploaded.append(
                await ingest_document(
                    store,
                    settings,
                    context=context,
                    filename=path.name,
                    declared_mime_type=mimetypes.guess_type(path.name)[0]
                    or "application/octet-stream",
                    content=content,
                )
            )
        upload_seconds = time.perf_counter() - upload_started

        submit_started = time.perf_counter()
        batch, document_ids = await submit_ingested_documents(store, context=context)
        submit_seconds = time.perf_counter() - submit_started

        process_timings: list[dict[str, Any]] = []
        processing_started = time.perf_counter()
        for document_id in document_ids:
            document = await store.get_row("documents", document_id)
            started = time.perf_counter()
            processing_error = None
            try:
                await DocumentProcessor(store, settings).process(document_id)
            except Exception as exc:
                processing_error = f"{type(exc).__name__}: {str(exc)[:300]}"
            elapsed = time.perf_counter() - started
            processed = await store.get_row("documents", document_id)
            extraction = await store.list_rows(
                "document_extractions", {"document_id": document_id}, limit=1
            )
            process_timings.append(
                {
                    "file": (document or {}).get("original_name"),
                    "document_type": (processed or {}).get("document_type"),
                    "status": (processed or {}).get("processing_status"),
                    "seconds": round(elapsed, 3),
                    "provider": extraction[0].get("provider") if extraction else None,
                    "model": extraction[0].get("model_name") if extraction else None,
                    "task_type": extraction[0].get("task_type") if extraction else None,
                    "fallback_reason": extraction[0].get("fallback_reason") if extraction else None,
                    "processing_error": processing_error,
                }
            )
        processing_seconds = time.perf_counter() - processing_started

        index_timings: list[dict[str, Any]] = []
        indexing_started = time.perf_counter()
        for document in await store.list_rows(
            "documents", {"application_id": context.application["id"]}
        ):
            chunks, elapsed = await _approve_and_index(store, settings, document)
            if document.get("document_type") in CLIENT_REQUIREMENTS:
                index_timings.append(
                    {
                        "file": document.get("original_name"),
                        "document_type": document.get("document_type"),
                        "chunks": chunks,
                        "seconds": round(elapsed, 3),
                    }
                )
        indexing_seconds = time.perf_counter() - indexing_started

        retrieval_started = time.perf_counter()
        retrieved_chunks = await retrieve_application_documents(
            store,
            settings,
            firm_id=DEMO_FIRM_ID,
            application_id=str(context.application["id"]),
            question="supplier invoice taxable value and GST evidence",
        )
        vector_retrieval = {
            "seconds": round(time.perf_counter() - retrieval_started, 3),
            "result_count": len(retrieved_chunks),
            "titles": [(row.get("metadata") or {}).get("title") for row in retrieved_chunks],
            "document_types": [row.get("document_type") for row in retrieved_chunks],
        }

        rag_timings: list[dict[str, Any]] = []
        assistant = RAGAssistant(store, settings)
        questions = (
            "What is the count of tax invoices?",
            "Which tax invoice has the lowest total invoice value?",
            "Summarize the Purchase Register and cite its source.",
        )
        for question in questions:
            started = time.perf_counter()
            answer = await assistant.query(
                question=question,
                firm_id=DEMO_FIRM_ID,
                application_id=str(context.application["id"]),
                user_id=DEMO_ADMIN_ID,
                conversation_id=str(uuid.uuid4()),
                source_type=None,
                role="firm_admin",
            )
            elapsed = time.perf_counter() - started
            rag_timings.append(
                {
                    "question": question,
                    "seconds": round(elapsed, 3),
                    "answer": answer.get("answer"),
                    "confidence": answer.get("confidence"),
                    "citation_count": len(answer.get("citations") or []),
                    "source_types": answer.get("source_types") or [],
                }
            )

        chunks = await store.list_rows(
            "document_chunks", {"application_id": context.application["id"]}
        )
        ground_truth_leaks = [
            row
            for row in chunks
            if "ground_truth" in str(row.get("content") or "").lower()
            or "ground_truth" in json.dumps(row.get("metadata") or {}).lower()
        ]
        failed = [row for row in process_timings if row["status"] == "processing_failed"]
        return {
            "dataset": dataset.name,
            "excluded_references": [path.name for path in dataset.excluded_references],
            "business_document_count": len(dataset.business_files),
            "input_profile": input_profile,
            "upload_seconds": round(upload_seconds, 3),
            "submit_response_seconds": round(submit_seconds, 3),
            "batch_id": batch["id"],
            "processing_seconds": round(processing_seconds, 3),
            "processing": process_timings,
            "indexing_seconds": round(indexing_seconds, 3),
            "indexing": index_timings,
            "vector_retrieval": vector_retrieval,
            "rag": rag_timings,
            "records": len(
                await store.list_rows(
                    "invoice_records", {"application_id": context.application["id"]}
                )
            ),
            "document_chunks": len(chunks),
            "ground_truth_chunk_count": len(ground_truth_leaks),
            "failed_documents": len(failed),
            "end_to_end_seconds": round(
                upload_seconds
                + submit_seconds
                + processing_seconds
                + indexing_seconds
                + vector_retrieval["seconds"]
                + sum(row["seconds"] for row in rag_timings),
                3,
            ),
        }


async def _run(args: argparse.Namespace) -> None:
    all_datasets = discover_dataset_sets(args.dataset_root.resolve())
    if len(all_datasets) != 3:
        raise ValueError(f"Expected exactly three dataset sets, found {len(all_datasets)}")
    datasets = (
        [dataset for dataset in all_datasets if args.only.lower() in dataset.name.lower()]
        if args.only
        else all_datasets
    )
    if not datasets:
        raise ValueError(f"No dataset matched --only={args.only!r}")
    settings = Settings(_env_file=args.env_file.resolve())
    if settings.ai_mode != "live":
        raise ValueError("Benchmark requires AI_MODE=live in the selected environment file")

    started = time.perf_counter()
    results = []
    for dataset in datasets:
        print(f"Benchmarking {dataset.name} ({len(dataset.business_files)} business files)...")
        result = await benchmark_set(dataset, settings)
        results.append(result)
        print(
            f"  upload={result['upload_seconds']:.3f}s "
            f"submit={result['submit_response_seconds']:.3f}s "
            f"process={result['processing_seconds']:.3f}s "
            f"index={result['indexing_seconds']:.3f}s "
            f"total={result['end_to_end_seconds']:.3f}s"
        )
        _write_report(args, settings, started, results, complete=False)
    _write_report(args, settings, started, results, complete=True)
    print(f"Benchmark report: {args.output.resolve()}")


def _write_report(
    args: argparse.Namespace,
    settings: Settings,
    started: float,
    results: list[dict[str, Any]],
    *,
    complete: bool,
) -> dict[str, Any]:
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "complete": complete,
        "dataset_root": str(args.dataset_root.resolve()),
        "ai_mode": settings.ai_mode,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "embedding_dimension": settings.embedding_dimension,
        "heavy_processing_concurrency": settings.heavy_processing_concurrency,
        "total_wall_seconds": round(time.perf_counter() - started, 3),
        "sets": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--only", help="Benchmark only dataset names containing this text")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".runtime/benchmarks/free-tier-pipeline.json"),
    )
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
