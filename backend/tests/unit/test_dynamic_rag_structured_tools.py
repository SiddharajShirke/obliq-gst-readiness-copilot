from __future__ import annotations

from decimal import Decimal

import pytest

from app.config import Settings
from app.repositories.memory import MemoryStore
from app.schemas.assistant_tools import QueryDomain, QueryFilter, QueryOperation, QueryPlan
from app.services.rag.structured_tools import execute_structured_plan


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore(Settings(app_env="test", use_in_memory_db=True, _env_file=None))


async def _record(
    store: MemoryStore,
    *,
    application_id: str,
    invoice_number: str,
    invoice_total: str,
    taxable_value: str,
    category: str = "purchase",
) -> dict:
    return await store.insert_row(
        "invoice_records",
        {
            "firm_id": "firm-1",
            "client_id": "client-1",
            "application_id": application_id,
            "invoice_category": category,
            "document_type": f"{category}_invoices",
            "invoice_number": invoice_number,
            "taxable_value": taxable_value,
            "total_tax": "180.00",
            "invoice_total": invoice_total,
            "review_status": "approved",
        },
    )


@pytest.mark.asyncio
async def test_transaction_count_is_application_scoped(store: MemoryStore) -> None:
    await _record(
        store,
        application_id="app-a",
        invoice_number="A-1",
        invoice_total="1180.00",
        taxable_value="1000.00",
    )
    await _record(
        store,
        application_id="app-a",
        invoice_number="A-2",
        invoice_total="2360.00",
        taxable_value="2000.00",
    )
    await _record(
        store,
        application_id="app-private",
        invoice_number="PRIVATE-1",
        invoice_total="999999.00",
        taxable_value="999999.00",
    )
    plan = QueryPlan(
        domain=QueryDomain.TRANSACTIONS,
        operation=QueryOperation.COUNT,
        filters=[QueryFilter(field="record_kind", value="tax_invoice")],
    )

    result = await execute_structured_plan(store, application_id="app-a", plan=plan)

    assert result.value == 2
    assert result.row_count == 2
    assert "PRIVATE-1" not in str(result.data)


@pytest.mark.asyncio
async def test_minimum_invoice_uses_decimal_and_returns_source_row(store: MemoryStore) -> None:
    await _record(
        store,
        application_id="app-a",
        invoice_number="HIGH-1",
        invoice_total="100.10",
        taxable_value="90.00",
    )
    lowest = await _record(
        store,
        application_id="app-a",
        invoice_number="LOW-1",
        invoice_total="9.99",
        taxable_value="8.00",
    )
    plan = QueryPlan(
        domain=QueryDomain.TRANSACTIONS,
        operation=QueryOperation.MINIMUM,
        metric="invoice_total",
        order_by="invoice_total",
        limit=1,
    )

    result = await execute_structured_plan(store, application_id="app-a", plan=plan)

    assert result.value == Decimal("9.99")
    assert result.data[0]["id"] == lowest["id"]
    assert result.citations[0]["source_type"] == "structured_fact"


@pytest.mark.asyncio
async def test_rcm_threshold_filters_exact_decimal_values(store: MemoryStore) -> None:
    low = await _record(
        store,
        application_id="app-a",
        invoice_number="LOW-RCM",
        invoice_total="49999.99",
        taxable_value="40000.00",
    )
    high = await _record(
        store,
        application_id="app-a",
        invoice_number="HIGH-RCM",
        invoice_total="50000.00",
        taxable_value="42000.00",
    )
    await store.update_row("invoice_records", low["id"], {"rcm_flag": True})
    await store.update_row("invoice_records", high["id"], {"rcm_flag": True})
    plan = QueryPlan(
        domain=QueryDomain.TRANSACTIONS,
        operation=QueryOperation.LIST,
        filters=[
            QueryFilter(field="rcm_flag", value=True),
            QueryFilter(field="invoice_total", operator="gte", value="50000"),
        ],
    )

    result = await execute_structured_plan(store, application_id="app-a", plan=plan)

    assert [row["invoice_number"] for row in result.data] == ["HIGH-RCM"]


@pytest.mark.asyncio
async def test_reconciliation_and_audit_tools_remain_application_scoped(
    store: MemoryStore,
) -> None:
    run = await store.insert_row(
        "reconciliation_runs",
        {"firm_id": "firm-1", "application_id": "app-a", "status": "completed"},
    )
    await store.insert_row(
        "reconciliation_items",
        {
            "reconciliation_run_id": run["id"],
            "match_status": "gstr2b_only",
            "evidence": {"gstr2b": {"invoice_number": "ONLY-2B"}},
        },
    )
    await store.insert_row(
        "audit_events",
        {"firm_id": "firm-1", "application_id": "app-a", "action": "document.approved"},
    )
    await store.insert_row(
        "audit_events",
        {"firm_id": "firm-1", "application_id": "app-private", "action": "private"},
    )

    reconciliation = await execute_structured_plan(
        store,
        application_id="app-a",
        plan=QueryPlan(
            domain=QueryDomain.RECONCILIATION,
            operation=QueryOperation.LIST,
            filters=[QueryFilter(field="match_status", value="gstr2b_only")],
        ),
    )
    audit = await execute_structured_plan(
        store,
        application_id="app-a",
        plan=QueryPlan(domain=QueryDomain.AUDIT, operation=QueryOperation.LIST),
    )

    assert reconciliation.data[0]["evidence"]["gstr2b"]["invoice_number"] == "ONLY-2B"
    assert [row["action"] for row in audit.data] == ["document.approved"]
