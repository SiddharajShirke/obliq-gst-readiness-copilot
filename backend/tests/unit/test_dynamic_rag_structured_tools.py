from __future__ import annotations

from decimal import Decimal

import pytest

from app.agents.rag_assistant import RAGAssistant
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
async def test_tax_invoice_filter_excludes_credit_and_debit_notes(
    store: MemoryStore,
) -> None:
    await _record(
        store,
        application_id="app-a",
        invoice_number="TAX-1",
        invoice_total="1180.00",
        taxable_value="1000.00",
    )
    credit_note = await _record(
        store,
        application_id="app-a",
        invoice_number="CN-1",
        invoice_total="-118.00",
        taxable_value="-100.00",
    )
    await store.update_row(
        "invoice_records",
        credit_note["id"],
        {"document_type": "Credit Note"},
    )
    plan = QueryPlan(
        domain=QueryDomain.TRANSACTIONS,
        operation=QueryOperation.COUNT,
        filters=[QueryFilter(field="record_kind", value="tax_invoice")],
    )

    result = await execute_structured_plan(store, application_id="app-a", plan=plan)

    assert result.value == 1
    assert [row["invoice_number"] for row in result.data] == ["TAX-1"]


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


@pytest.mark.asyncio
async def test_assistant_answers_dynamic_count_and_minimum_without_generic_snapshot(
    store: MemoryStore,
) -> None:
    application_id = "30000000-0000-0000-0000-000000000001"
    await _record(
        store,
        application_id=application_id,
        invoice_number="DYNAMIC-HIGH",
        invoice_total="1180.00",
        taxable_value="1000.00",
    )
    await _record(
        store,
        application_id=application_id,
        invoice_number="DYNAMIC-LOW",
        invoice_total="590.00",
        taxable_value="500.00",
    )
    assistant = RAGAssistant(
        store,
        Settings(app_env="test", ai_mode="mock", use_in_memory_db=True, _env_file=None),
    )

    count_answer = await assistant.query(
        question="What is count of tax invoices?",
        firm_id="11111111-1111-1111-1111-111111111111",
        application_id=application_id,
        user_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        conversation_id="dynamic-count",
        source_type=None,
    )
    minimum_answer = await assistant.query(
        question="Which tax invoice has the lowest total invoice value?",
        firm_id="11111111-1111-1111-1111-111111111111",
        application_id=application_id,
        user_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        conversation_id="dynamic-minimum",
        source_type=None,
    )

    assert "2" in count_answer["answer"]
    assert "tax invoice" in count_answer["answer"].lower()
    assert "application review snapshot" not in count_answer["answer"].lower()
    assert count_answer["calculation"] == {
        "operation": "count",
        "metric": None,
        "value": 2,
        "record_count": 2,
    }
    assert "DYNAMIC-LOW" in minimum_answer["answer"]
    assert "590.00" in minimum_answer["answer"]
    assert minimum_answer["calculation"]["operation"] == "minimum"
    assert minimum_answer["rows"][0]["invoice_number"] == "DYNAMIC-LOW"
