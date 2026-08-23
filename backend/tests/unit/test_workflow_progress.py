import pytest

from app.config import Settings
from app.repositories.memory import DEMO_FIRM_ID, MemoryStore
from app.services.workflow_progress import get_workflow_progress

APP_ID = "30000000-0000-0000-0000-000000000001"


@pytest.mark.asyncio
async def test_workflow_progress_uses_live_review_and_validation_counts(tmp_path) -> None:
    store = MemoryStore(Settings(local_data_dir=tmp_path))
    requirements = await store.list_rows("document_requirements", {"application_id": APP_ID})
    for requirement in requirements:
        await store.update_row("document_requirements", requirement["id"], {"status": "received"})
    await store.insert_row(
        "invoice_records",
        {
            "id": "approved-record",
            "firm_id": DEMO_FIRM_ID,
            "application_id": APP_ID,
            "client_id": "20000000-0000-0000-0000-000000000001",
            "review_status": "approved",
        },
    )
    await store.insert_row(
        "invoice_records",
        {
            "id": "pending-record",
            "firm_id": DEMO_FIRM_ID,
            "application_id": APP_ID,
            "client_id": "20000000-0000-0000-0000-000000000001",
            "review_status": "pending",
        },
    )
    await store.update_row("applications", APP_ID, {"status": "extraction_review"})

    progress = await get_workflow_progress(store, APP_ID)

    assert progress["current_stage"] == "extraction_review"
    assert progress["extraction"]["reviewed_count"] == 1
    assert progress["extraction"]["pending_count"] == 1
    extraction = next(step for step in progress["steps"] if step["key"] == "extraction_review")
    assert extraction["state"] == "current"
    assert extraction["progress_percent"] == 50
    assert progress["progress_percent"] == 62


@pytest.mark.asyncio
async def test_workflow_progress_advances_to_validation_from_live_findings(tmp_path) -> None:
    store = MemoryStore(Settings(local_data_dir=tmp_path))
    requirements = await store.list_rows("document_requirements", {"application_id": APP_ID})
    for requirement in requirements:
        await store.update_row("document_requirements", requirement["id"], {"status": "received"})
    await store.insert_row(
        "invoice_records",
        {
            "id": "approved-record",
            "firm_id": DEMO_FIRM_ID,
            "application_id": APP_ID,
            "client_id": "20000000-0000-0000-0000-000000000001",
            "review_status": "approved",
        },
    )
    await store.insert_row(
        "validation_findings",
        {
            "id": "finding",
            "firm_id": DEMO_FIRM_ID,
            "application_id": APP_ID,
            "invoice_record_id": "approved-record",
            "finding_type": "missing_invoice_date",
            "severity": "high",
            "message": "Date missing",
            "status": "open",
        },
    )
    await store.update_row("applications", APP_ID, {"status": "validation_review"})

    progress = await get_workflow_progress(store, APP_ID)

    assert progress["current_stage"] == "validation_review"
    assert progress["validation"]["open_count"] == 1
    assert (
        next(step for step in progress["steps"] if step["key"] == "extraction_review")["state"]
        == "completed"
    )
    assert (
        next(step for step in progress["steps"] if step["key"] == "validation_review")["state"]
        == "current"
    )


@pytest.mark.asyncio
async def test_reconciliation_progress_uses_only_latest_run(tmp_path) -> None:
    store = MemoryStore(Settings(local_data_dir=tmp_path))
    requirements = await store.list_rows("document_requirements", {"application_id": APP_ID})
    for requirement in requirements:
        await store.update_row("document_requirements", requirement["id"], {"status": "received"})
    await store.insert_row(
        "invoice_records",
        {
            "id": "approved-record",
            "firm_id": DEMO_FIRM_ID,
            "application_id": APP_ID,
            "client_id": "20000000-0000-0000-0000-000000000001",
            "review_status": "approved",
        },
    )
    for run_id, created_at, review_status in (
        ("old-run", "2026-08-20T00:00:00+00:00", "reviewed"),
        ("new-run", "2026-08-21T00:00:00+00:00", "pending"),
    ):
        await store.insert_row(
            "reconciliation_runs",
            {
                "id": run_id,
                "firm_id": DEMO_FIRM_ID,
                "application_id": APP_ID,
                "created_at": created_at,
            },
        )
        await store.insert_row(
            "reconciliation_items",
            {
                "id": f"item-{run_id}",
                "reconciliation_run_id": run_id,
                "review_status": review_status,
            },
        )
    await store.update_row("applications", APP_ID, {"status": "reconciliation_review"})

    progress = await get_workflow_progress(store, APP_ID)

    assert progress["reconciliation"]["run_count"] == 2
    assert progress["reconciliation"]["item_count"] == 1
    assert progress["reconciliation"]["open_count"] == 1


@pytest.mark.asyncio
async def test_validation_completion_makes_ready_for_filing_without_reconciliation(
    tmp_path,
) -> None:
    store = MemoryStore(Settings(local_data_dir=tmp_path))
    requirements = await store.list_rows("document_requirements", {"application_id": APP_ID})
    for requirement in requirements:
        await store.update_row("document_requirements", requirement["id"], {"status": "received"})
    await store.insert_row(
        "invoice_records",
        {
            "id": "ready-record",
            "firm_id": DEMO_FIRM_ID,
            "application_id": APP_ID,
            "client_id": "20000000-0000-0000-0000-000000000001",
            "review_status": "approved",
        },
    )
    await store.insert_row(
        "validation_findings",
        {
            "id": "resolved-finding",
            "firm_id": DEMO_FIRM_ID,
            "application_id": APP_ID,
            "invoice_record_id": "ready-record",
            "finding_type": "missing_invoice_date",
            "severity": "high",
            "message": "Date reviewed",
            "status": "resolved",
        },
    )
    await store.update_row("applications", APP_ID, {"status": "validation_review"})

    progress = await get_workflow_progress(store, APP_ID)

    assert progress["validation"]["progress_percent"] == 100
    assert progress["readiness"] == {
        "ready_for_filing": True,
        "ready_for_filing_percent": 100,
        "main_export_enabled": True,
    }
    assert progress["reconciliation"]["available"] is True
    assert progress["reconciliation"]["progress_percent"] == 0
    assert progress["reconciliation"]["export_enabled"] is False
    ready_step = next(step for step in progress["steps"] if step["key"] == "ready_for_filing")
    assert ready_step["state"] == "completed"


@pytest.mark.asyncio
async def test_incomplete_reconciliation_does_not_reduce_ready_for_filing(tmp_path) -> None:
    store = MemoryStore(Settings(local_data_dir=tmp_path))
    await store.insert_row(
        "invoice_records",
        {
            "id": "approved-ready-record",
            "firm_id": DEMO_FIRM_ID,
            "application_id": APP_ID,
            "client_id": "20000000-0000-0000-0000-000000000001",
            "review_status": "approved",
        },
    )
    await store.insert_row(
        "validation_findings",
        {
            "id": "accepted-finding",
            "firm_id": DEMO_FIRM_ID,
            "application_id": APP_ID,
            "invoice_record_id": "approved-ready-record",
            "finding_type": "future_date",
            "severity": "medium",
            "message": "Accepted for CA review",
            "status": "accepted",
        },
    )
    run = await store.insert_row(
        "reconciliation_runs",
        {
            "id": "branch-run",
            "firm_id": DEMO_FIRM_ID,
            "application_id": APP_ID,
            "status": "completed",
            "created_at": "2026-08-23T10:00:00+00:00",
        },
    )
    await store.insert_row(
        "reconciliation_items",
        {
            "id": "branch-mismatch",
            "reconciliation_run_id": run["id"],
            "match_status": "value_mismatch",
            "review_status": "pending",
        },
    )
    await store.update_row("applications", APP_ID, {"status": "reconciliation_review"})

    progress = await get_workflow_progress(store, APP_ID)

    assert progress["readiness"]["ready_for_filing"] is True
    assert progress["readiness"]["ready_for_filing_percent"] == 100
    assert progress["reconciliation"]["progress_percent"] == 0
    assert progress["reconciliation"]["export_enabled"] is False


@pytest.mark.asyncio
async def test_completed_reconciliation_with_only_exact_matches_is_exportable(tmp_path) -> None:
    store = MemoryStore(Settings(local_data_dir=tmp_path))
    await store.update_row("applications", APP_ID, {"status": "ready_for_filing"})
    run = await store.insert_row(
        "reconciliation_runs",
        {
            "id": "exact-run",
            "firm_id": DEMO_FIRM_ID,
            "application_id": APP_ID,
            "status": "completed",
            "created_at": "2026-08-23T11:00:00+00:00",
        },
    )
    await store.insert_row(
        "reconciliation_items",
        {
            "id": "exact-item",
            "reconciliation_run_id": run["id"],
            "match_status": "exact_match",
            "review_status": "pending",
        },
    )

    progress = await get_workflow_progress(store, APP_ID)

    assert progress["reconciliation"]["review_required_count"] == 0
    assert progress["reconciliation"]["progress_percent"] == 100
    assert progress["reconciliation"]["export_enabled"] is True
