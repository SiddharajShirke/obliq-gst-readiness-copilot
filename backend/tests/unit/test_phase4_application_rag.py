from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from app.repositories import get_store
from app.services.rag.embeddings import DeterministicEmbeddingProvider

DEMO_FIRM_ID = "11111111-1111-1111-1111-111111111111"
RAJ_APPLICATION_ID = "30000000-0000-0000-0000-000000000001"
ABC_APPLICATION_ID = "30000000-0000-0000-0000-000000000002"


@pytest.mark.asyncio
async def test_application_chunk_search_is_scoped_and_excludes_ground_truth() -> None:
    store = get_store()
    settings = get_settings()
    query = DeterministicEmbeddingProvider(384).embed_texts(
        ["EFI 0826 889 taxable value mismatch"]
    )[0]
    marker = uuid.uuid4().hex

    for application_id, document_type, content in (
        (
            RAJ_APPLICATION_ID,
            "purchase_register",
            f"{marker} EFI/0826/889 books taxable value 90000",
        ),
        (ABC_APPLICATION_ID, "purchase_register", f"{marker} another client private invoice"),
        (
            RAJ_APPLICATION_ID,
            "developer_ground_truth",
            f"{marker} expected answers must never leak",
        ),
    ):
        await store.insert_row(
            "document_chunks",
            {
                "firm_id": DEMO_FIRM_ID,
                "client_id": str(uuid.uuid4()),
                "application_id": application_id,
                "demo_session_id": None,
                "document_id": str(uuid.uuid4()),
                "document_type": document_type,
                "chunk_index": 0,
                "content": content,
                "metadata": {"title": "Evidence"},
                "checksum": uuid.uuid4().hex,
                "embedding": query,
                "embedding_model": settings.embedding_model,
            },
        )

    results = await store.rpc(
        "match_application_document_chunks",
        {
            "query_embedding": query,
            "user_firm_id": DEMO_FIRM_ID,
            "target_application_id": RAJ_APPLICATION_ID,
            "match_count": 10,
            "min_similarity": 0.0,
        },
    )

    marked_results = [row for row in results if marker in row["content"]]
    assert len(marked_results) == 1
    assert marked_results[0]["application_id"] == RAJ_APPLICATION_ID
    assert marked_results[0]["document_type"] == "purchase_register"


@pytest.mark.asyncio
async def test_approved_extraction_is_indexed_with_row_provenance_idempotently() -> None:
    from app.services.rag.document_indexing import index_document

    store = get_store()
    settings = get_settings()
    document = await store.insert_row(
        "documents",
        {
            "firm_id": DEMO_FIRM_ID,
            "client_id": "20000000-0000-0000-0000-000000000001",
            "application_id": RAJ_APPLICATION_ID,
            "demo_session_id": None,
            "original_name": "Purchase_Register_August.xlsx",
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "storage_path": "phase4/purchase.xlsx",
            "file_size": 100,
            "sha256": uuid.uuid4().hex,
            "document_type": "purchase_register",
            "processing_status": "approved",
            "source": "dashboard",
        },
    )
    await store.insert_row(
        "document_extractions",
        {
            "document_id": document["id"],
            "document_type": "purchase_register",
            "raw_text": "",
            "structured_data": {"summary": {"record_count": 1}},
            "original_structured_data": {"summary": {"record_count": 1}},
            "review_status": "approved",
        },
    )
    await store.insert_row(
        "invoice_records",
        {
            "firm_id": DEMO_FIRM_ID,
            "client_id": document["client_id"],
            "application_id": RAJ_APPLICATION_ID,
            "document_id": document["id"],
            "invoice_category": "purchase",
            "document_type": "purchase_register",
            "supplier_name": "Everest Fasteners India",
            "supplier_gstin": "27ABCDE1234F1Z5",
            "invoice_number": "EFI/0826/889",
            "invoice_date": "2026-08-12",
            "taxable_value": "90000.00",
            "cgst": "8100.00",
            "sgst": "8100.00",
            "igst": None,
            "cess": None,
            "source_row": 7,
            "source_page": None,
            "review_status": "approved",
        },
    )

    first = await index_document(store, settings, document["id"])
    second = await index_document(store, settings, document["id"])

    assert len(first) == len(second) == 1
    assert first[0]["id"] == second[0]["id"]
    assert first[0]["row_start"] == 7
    assert first[0]["row_end"] == 7
    assert "EFI/0826/889" in first[0]["content"]
    assert "90000.00" in first[0]["content"]


@pytest.mark.asyncio
async def test_ground_truth_document_is_never_indexed() -> None:
    from app.services.rag.document_indexing import index_document

    store = get_store()
    settings = get_settings()
    document = await store.insert_row(
        "documents",
        {
            "firm_id": DEMO_FIRM_ID,
            "client_id": "20000000-0000-0000-0000-000000000001",
            "application_id": RAJ_APPLICATION_ID,
            "demo_session_id": None,
            "original_name": "00_Set_Index_and_Ground_Truth.pdf",
            "mime_type": "application/pdf",
            "storage_path": "phase4/ground-truth.pdf",
            "file_size": 100,
            "sha256": uuid.uuid4().hex,
            "document_type": "developer_ground_truth",
            "processing_status": "excluded_reference",
            "source": "dashboard",
        },
    )

    assert await index_document(store, settings, document["id"]) == []
    assert await store.list_rows("document_chunks", {"document_id": document["id"]}) == []


@pytest.mark.asyncio
async def test_structured_context_uses_only_the_selected_application() -> None:
    from app.services.rag.application_context import load_structured_facts

    store = get_store()
    raj_record = await store.insert_row(
        "invoice_records",
        {
            "firm_id": DEMO_FIRM_ID,
            "client_id": "20000000-0000-0000-0000-000000000001",
            "application_id": RAJ_APPLICATION_ID,
            "document_id": None,
            "invoice_category": "purchase",
            "invoice_number": "PHASE4/RAJ/001",
            "invoice_number_normalized": "PHASE4RAJ001",
            "taxable_value": "12500.00",
            "review_status": "approved",
        },
    )
    await store.insert_row(
        "invoice_records",
        {
            "firm_id": DEMO_FIRM_ID,
            "client_id": "20000000-0000-0000-0000-000000000002",
            "application_id": ABC_APPLICATION_ID,
            "document_id": None,
            "invoice_category": "purchase",
            "invoice_number": "PHASE4/ABC/PRIVATE",
            "invoice_number_normalized": "PHASE4ABCPRIVATE",
            "taxable_value": "999999.00",
            "review_status": "approved",
        },
    )

    facts = await load_structured_facts(
        store,
        application_id=RAJ_APPLICATION_ID,
        question="What is the taxable value for PHASE4/RAJ/001?",
        intent="transaction_lookup",
    )

    assert facts["collection"]["required_count"] == 6
    assert [row["id"] for row in facts["transactions"]] == [raj_record["id"]]
    assert "PHASE4/ABC/PRIVATE" not in str(facts)


@pytest.mark.asyncio
async def test_raised_alerts_are_distinct_from_unraised_reconciliation_findings() -> None:
    from app.services.rag.application_context import load_structured_facts

    store = get_store()
    run = await store.insert_row(
        "reconciliation_runs",
        {
            "firm_id": DEMO_FIRM_ID,
            "application_id": RAJ_APPLICATION_ID,
            "status": "completed",
            "summary": {"value_mismatch": 2},
        },
    )
    raised_item = await store.insert_row(
        "reconciliation_items",
        {
            "reconciliation_run_id": run["id"],
            "match_status": "value_mismatch",
            "match_score": "0.8",
            "differences": {"taxable_value": {"books": "90000.00", "gstr2b": "95000.00"}},
            "evidence": {
                "books": {"invoice_number": "RAISED/001"},
                "gstr2b": {"invoice_number": "RAISED/001"},
            },
            "special_flags": [],
            "review_status": "pending",
        },
    )
    unraised_item = await store.insert_row(
        "reconciliation_items",
        {
            "reconciliation_run_id": run["id"],
            "match_status": "books_only",
            "match_score": "0",
            "differences": {},
            "evidence": {"books": {"invoice_number": "UNRAISED/002"}, "gstr2b": None},
            "special_flags": [],
            "review_status": "pending",
        },
    )
    alert = await store.insert_row(
        "alerts",
        {
            "firm_id": DEMO_FIRM_ID,
            "application_id": RAJ_APPLICATION_ID,
            "client_id": "20000000-0000-0000-0000-000000000001",
            "reconciliation_item_id": raised_item["id"],
            "alert_type": "TAXABLE_VALUE_MISMATCH",
            "title": "Taxable Value Mismatch",
            "message": "Raised by the CA",
            "severity": "medium",
            "status": "open",
            "evidence": {},
        },
    )

    facts = await load_structured_facts(
        store,
        application_id=RAJ_APPLICATION_ID,
        question="Which reconciliation findings have been raised as alerts?",
        intent="alerts",
    )

    alert_ids = {row["id"] for row in facts["alerts"]}
    linked_item_ids = {row.get("reconciliation_item_id") for row in facts["alerts"]}
    assert alert["id"] in alert_ids
    assert unraised_item["id"] not in linked_item_ids
    assert len(facts["reconciliation"]["items"]) == 2


@pytest.mark.asyncio
async def test_live_exact_reconciliation_answer_does_not_send_case_data_to_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agents.rag_assistant import RAGAssistant

    settings = get_settings().model_copy(update={"ai_mode": "live"})
    called = False

    async def fail_if_called(*args: object, **kwargs: object) -> dict[str, object]:
        nonlocal called
        called = True
        raise AssertionError("Exact deterministic reconciliation must not call Groq")

    monkeypatch.setattr(
        "app.agents.rag_assistant.complete_groq_json",
        fail_if_called,
    )
    state = {
        "intent": "reconciliation",
        "question": "Why is MOM/0726/784 flagged?",
        "application_data": {
            "reconciliation_item": {
                "match_status": "value_mismatch",
                "differences": {
                    "taxable_value": {"books": "90000.00", "gstr2b": "95000.00"}
                },
                "evidence": {
                    "books": {"invoice_number": "MOM/0726/784"},
                    "gstr2b": {"invoice_number": "MOM/0726/784"},
                },
            },
            "reconciliation": {
                "items": [{"unrelated_payload": "x" * 500_000}],
            },
        },
    }

    result = await RAGAssistant(get_store(), settings).generate_grounded_answer(state)

    assert called is False
    assert "MOM/0726/784" in result["draft_answer"]
    assert "90000.00" in result["draft_answer"]
    assert "95000.00" in result["draft_answer"]


def test_guidance_payload_is_bounded_and_excludes_unselected_reconciliation_items() -> None:
    import json

    from app.agents.rag_assistant import RAGAssistant

    payload = RAGAssistant._compact_model_payload(
        {
            "question": "Explain the applicable review guidance",
            "history": [{"role": "user", "content": "h" * 50_000}],
            "application_data": {
                "application": {"id": RAJ_APPLICATION_ID, "period_label": "August 2026"},
                "client": {"business_name": "Raj Traders"},
                "reconciliation": {
                    "status": "completed",
                    "summary": {"value_mismatch": 1},
                    "items": [{"private_unselected_record": "x" * 500_000}],
                },
            },
            "application_evidence": [{"content": "a" * 50_000}],
            "knowledge_evidence": [{"content": "k" * 50_000}],
        }
    )
    encoded = json.dumps(payload)

    assert "private_unselected_record" not in encoded
    assert len(payload["conversation_history"][0]["content"]) == 1000
    assert len(payload["application_evidence"][0]["content"]) == 1200
    assert len(payload["knowledge_evidence"][0]["content"]) == 1200
    assert len(encoded) < 10_000


@pytest.mark.asyncio
async def test_uncited_model_answer_is_replaced_with_grounded_abstention() -> None:
    from app.agents.rag_assistant import RAGAssistant

    state = {
        "intent": "guidance",
        "draft_answer": "Invented uncited GST conclusion",
        "confidence": 0.9,
        "conversation_id": str(uuid.uuid4()),
        "application_data": {"application": {"period_label": "August 2026"}},
        "application_evidence": [],
        "knowledge_evidence": [],
    }

    result = await RAGAssistant(
        get_store(), get_settings()
    ).verify_scope_and_citations(state)

    assert "enough scoped evidence" in result["answer"]["answer"]
    assert result["answer"]["citations"] == []
    assert result["answer"]["confidence"] <= 0.25
