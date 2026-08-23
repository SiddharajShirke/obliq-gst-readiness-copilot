from __future__ import annotations

import asyncio
import time
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
async def test_document_indexing_uses_guarded_async_embeddings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.rag import document_indexing

    sync_calls = 0
    async_calls = 0

    def inline_embedding(*args: object, **kwargs: object) -> list[list[float]]:
        nonlocal sync_calls
        sync_calls += 1
        return [[0.0] * 384]

    async def guarded_embedding(
        texts: list[str], *args: object, **kwargs: object
    ) -> list[list[float]]:
        nonlocal async_calls
        async_calls += 1
        return [[0.0] * 384 for _ in texts]

    document = {
        "id": "document-1",
        "firm_id": "firm-1",
        "client_id": "client-1",
        "application_id": "application-1",
        "demo_session_id": None,
        "document_type": "purchase_register",
        "processing_status": "approved",
        "original_name": "Purchase Register.pdf",
    }

    class FakeStore:
        async def get_row(self, table: str, row_id: str) -> dict[str, object] | None:
            return document if table == "documents" else None

        async def list_rows(
            self, table: str, *args: object, **kwargs: object
        ) -> list[dict[str, object]]:
            if table == "document_extractions":
                return [{"id": "extraction-1", "review_status": "approved"}]
            return []

        async def insert_row(
            self, table: str, row: dict[str, object]
        ) -> dict[str, object]:
            return {"id": "chunk-1", **row}

        async def delete_row(self, table: str, row_id: str) -> None:
            return None

    async def source_chunks(*args: object, **kwargs: object) -> list[dict[str, object]]:
        return [{
            "content": "Invoice PR/001 taxable value 1000",
            "page_number": 1,
            "sheet_name": None,
            "row_start": None,
            "row_end": None,
            "section": "PR/001",
            "metadata": {"title": "Purchase Register.pdf"},
        }]

    monkeypatch.setattr(document_indexing, "_source_chunks", source_chunks)
    monkeypatch.setattr(
        document_indexing, "embed_texts", inline_embedding, raising=False
    )
    monkeypatch.setattr(
        document_indexing, "embed_texts_async", guarded_embedding, raising=False
    )

    await document_indexing.index_document(
        FakeStore(),  # type: ignore[arg-type]
        get_settings(),
        "document-1",
    )

    assert async_calls == 1
    assert sync_calls == 0


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


@pytest.mark.asyncio
async def test_vague_alert_followup_uses_existing_explanation_without_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches vague alert follow-ups falling into the slow general-RAG path."""
    from app.agents.rag_assistant import RAGAssistant

    assistant = RAGAssistant(
        get_store(), get_settings().model_copy(update={"ai_mode": "live"})
    )
    classified = await assistant.classify_question(
        {"question": "What does this response mean?"}
    )

    async def fail_if_called(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("Existing alert evidence must not be sent to Groq")

    monkeypatch.setattr(
        "app.agents.rag_assistant.complete_groq_json",
        fail_if_called,
    )
    state = {
        "intent": classified["intent"],
        "question": "What does this response mean?",
        "application_data": {
            "alerts": [
                {
                    "id": "591c79b9-11f5-4507-b1b8-83e537a9f918",
                    "title": "Value Mismatch",
                    "alert_type": "VALUE_MISMATCH",
                    "status": "open",
                    "evidence": {
                        "books": {
                            "invoice_number": "CG/0726/441",
                            "itc_status": "Claim subject to conditions",
                        },
                        "gstr2b": {
                            "invoice_number": "CG/0726/441",
                            "itc_status": "Available",
                        },
                        "difference_fields": ["itc_status"],
                    },
                    "ai_explanation": {
                        "what_happened": (
                            "The ITC status differs between the books and GSTR-2B."
                        ),
                        "why_flagged": "The compared ITC status fields are not equal.",
                        "what_ca_should_review": (
                            "Review invoice CG/0726/441 before deciding the ITC treatment."
                        ),
                        "short_summary": "ITC status mismatch requires CA review.",
                    },
                }
            ]
        },
    }

    result = await assistant.generate_grounded_answer(state)

    assert classified["intent"] == "alert_explanation"
    assert "CG/0726/441" in result["draft_answer"]
    assert "ITC status" in result["draft_answer"]
    assert "CA review" in result["draft_answer"]
    assert result["confidence"] >= 0.9


@pytest.mark.asyncio
async def test_definitional_gstr2b_question_uses_knowledge_guidance_intent() -> None:
    from app.agents.rag_assistant import RAGAssistant

    assistant = RAGAssistant(get_store(), get_settings())

    classified = await assistant.classify_question(
        {"question": "What does a GSTR-2B mismatch mean?"}
    )

    assert classified["intent"] == "guidance"
    assert classified["query_plan"].domain == "knowledge"


@pytest.mark.asyncio
async def test_live_guidance_timeout_returns_grounded_evidence_within_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches a slow Groq call consuming the assistant latency budget."""
    from app.agents.rag_assistant import RAGAssistant

    settings = get_settings().model_copy(
        update={"ai_mode": "live", "rag_generation_timeout_seconds": 0.01}
    )

    async def slow_model(*args: object, **kwargs: object) -> dict[str, object]:
        await asyncio.sleep(0.2)
        return {"answer": "Late model answer", "confidence": 0.9}

    monkeypatch.setattr("app.agents.rag_assistant.complete_groq_json", slow_model)
    state = {
        "intent": "guidance",
        "question": "Explain the applicable review guidance",
        "application_data": {},
        "application_evidence": [],
        "knowledge_evidence": [
            {
                "content": (
                    "A reconciliation mismatch requires CA review of the source records."
                )
            }
        ],
        "history": [],
    }
    started = time.perf_counter()

    result = await RAGAssistant(get_store(), settings).generate_grounded_answer(state)

    assert time.perf_counter() - started < 0.1
    assert "requires CA review" in result["draft_answer"]
    assert "temporarily unavailable" not in result["draft_answer"]
    assert result["confidence"] > 0


@pytest.mark.asyncio
async def test_live_guidance_failure_falls_back_to_structured_application_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches a provider failure degrading valid structured facts to a 0% answer."""
    from app.agents.rag_assistant import RAGAssistant

    async def failed_model(*args: object, **kwargs: object) -> dict[str, object]:
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("app.agents.rag_assistant.complete_groq_json", failed_model)
    settings = get_settings().model_copy(update={"ai_mode": "live"})
    state = {
        "intent": "guidance",
        "question": "Explain the applicable review guidance",
        "application_data": {
            "application": {"period_label": "May 2026"},
            "client": {"business_name": "Raj Traders"},
            "collection": {
                "required_count": 6,
                "received_count": 6,
                "missing_count": 0,
                "progress_percent": 100,
                "workflow_status": "documents_complete",
            },
            "extraction_summary": {
                "categories": [{"record_count": 12, "needs_review": 3}]
            },
            "validation_findings": [{"id": "finding-1"}],
            "reconciliation": {"summary": {"needs_review": 2}},
            "alerts": [{"id": "alert-1"}],
        },
        "application_evidence": [],
        "knowledge_evidence": [],
        "history": [],
    }

    result = await RAGAssistant(get_store(), settings).generate_grounded_answer(state)

    assert "Raj Traders" in result["draft_answer"]
    assert "6/6" in result["draft_answer"]
    assert "3 need CA review" in result["draft_answer"]
    assert "1 raised alert" in result["draft_answer"]
    assert result["confidence"] > 0


@pytest.mark.asyncio
async def test_live_guidance_without_text_evidence_uses_exact_facts_without_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches exact database facts being sent to a model with no retrieved text."""
    from app.agents.rag_assistant import RAGAssistant

    model_calls = 0

    async def unexpected_model(*args: object, **kwargs: object) -> dict[str, object]:
        nonlocal model_calls
        model_calls += 1
        return {"answer": "Unnecessary model answer", "confidence": 0.9}

    monkeypatch.setattr("app.agents.rag_assistant.complete_groq_json", unexpected_model)
    settings = get_settings().model_copy(update={"ai_mode": "live"})
    state = {
        "intent": "guidance",
        "question": "Give the current application review snapshot",
        "application_data": {
            "application": {"period_label": "May 2026"},
            "client": {"business_name": "Raj Traders"},
            "collection": {
                "required_count": 6,
                "received_count": 6,
                "progress_percent": 100,
            },
            "extraction_summary": {"categories": []},
            "validation_findings": [],
            "reconciliation": {"summary": {}},
            "alerts": [],
        },
        "application_evidence": [],
        "knowledge_evidence": [],
        "history": [],
    }

    result = await RAGAssistant(get_store(), settings).generate_grounded_answer(state)

    assert model_calls == 0
    assert "Raj Traders" in result["draft_answer"]
    assert "6/6" in result["draft_answer"]


@pytest.mark.asyncio
async def test_embedding_warmup_loads_and_encodes_before_serving(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches the local embedding model remaining cold until the first RAG request."""
    from app.services.rag.embeddings import warm_embedding_provider

    encoded: list[list[str]] = []

    class FakeProvider:
        dimension = 384

        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            encoded.append(texts)
            return [[0.0] * self.dimension for _ in texts]

    monkeypatch.setattr(
        "app.services.rag.embeddings.get_embedding_provider",
        lambda settings: FakeProvider(),
    )

    await warm_embedding_provider(get_settings())

    assert encoded == [["OBLIQ embedding warmup"]]


@pytest.mark.asyncio
async def test_question_retrieval_does_not_rescan_and_reindex_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches per-question document rescans that create N+1 Supabase latency."""
    from app.agents.rag_assistant import RAGAssistant

    async def fail_if_rescanned(*args: object, **kwargs: object) -> int:
        raise AssertionError("Document indexing belongs to extraction review, not a question")

    async def scoped_results(*args: object, **kwargs: object) -> list[dict[str, object]]:
        return [{"content": "Approved application evidence"}]

    monkeypatch.setattr(
        "app.services.rag.document_indexing.sync_application_documents",
        fail_if_rescanned,
    )
    monkeypatch.setattr(
        "app.agents.rag_assistant.retrieve_application_documents",
        scoped_results,
    )

    result = await RAGAssistant(
        get_store(), get_settings()
    ).retrieve_application_evidence(
        {
            "intent": "guidance",
            "question": "Explain the review guidance",
            "firm_id": DEMO_FIRM_ID,
            "application_id": RAJ_APPLICATION_ID,
        }
    )

    assert result == {"application_evidence": [{"content": "Approved application evidence"}]}


@pytest.mark.asyncio
async def test_guidance_structured_fact_reads_run_concurrently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches independent Supabase fact reads becoming a sequential latency chain."""
    from app.services.rag.application_context import load_structured_facts

    class FakeStore:
        async def get_row(self, table: str, row_id: str) -> dict[str, object]:
            if table == "applications":
                return {
                    "id": row_id,
                    "client_id": "client-1",
                    "period_label": "May 2026",
                }
            return {"id": row_id, "business_name": "Raj Traders"}

    async def delayed(value: object) -> object:
        await asyncio.sleep(0.08)
        return value

    monkeypatch.setattr(
        "app.services.rag.application_context.get_document_collection_status",
        lambda *args, **kwargs: delayed({"requirements": []}),
    )
    monkeypatch.setattr(
        "app.services.rag.application_context.get_extraction_summary",
        lambda *args, **kwargs: delayed({"categories": []}),
    )
    monkeypatch.setattr(
        "app.services.rag.application_context.get_transaction_record",
        lambda *args, **kwargs: delayed([]),
    )
    monkeypatch.setattr(
        "app.services.rag.application_context.get_validation_findings",
        lambda *args, **kwargs: delayed([]),
    )
    monkeypatch.setattr(
        "app.services.rag.application_context.get_reconciliation_overview",
        lambda *args, **kwargs: delayed({"summary": {}}),
    )
    monkeypatch.setattr(
        "app.services.rag.application_context.list_application_alerts",
        lambda *args, **kwargs: delayed([]),
    )
    started = time.perf_counter()

    result = await load_structured_facts(
        FakeStore(),
        application_id=RAJ_APPLICATION_ID,
        question="Explain the applicable review guidance",
        intent="guidance",
    )

    assert time.perf_counter() - started < 0.2
    assert result["alerts"] == []


@pytest.mark.asyncio
async def test_guidance_avoids_full_transaction_and_reconciliation_item_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches overview guidance loading every invoice and reconciliation item."""
    from app.services.rag.application_context import load_structured_facts

    requested_tables: list[str] = []

    class FakeStore:
        async def get_row(self, table: str, row_id: str) -> dict[str, object]:
            if table == "applications":
                return {
                    "id": row_id,
                    "client_id": "client-1",
                    "period_label": "May 2026",
                }
            return {"id": row_id, "business_name": "Raj Traders"}

        async def list_rows(
            self, table: str, *args: object, **kwargs: object
        ) -> list[dict[str, object]]:
            requested_tables.append(table)
            if table == "reconciliation_runs":
                return [{"id": "run-1", "summary": {"exact_match": 1}}]
            return []

    monkeypatch.setattr(
        "app.services.rag.application_context.get_document_collection_status",
        lambda *args, **kwargs: asyncio.sleep(0, result={"requirements": []}),
    )

    result = await load_structured_facts(
        FakeStore(),  # type: ignore[arg-type]
        application_id=RAJ_APPLICATION_ID,
        question="Explain the applicable review guidance",
        intent="guidance",
    )

    assert "transactions" not in result
    assert "reconciliation_items" not in requested_tables


@pytest.mark.asyncio
async def test_structured_facts_reuse_access_checked_application_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches the same application row being fetched again after access validation."""
    from app.services.rag.application_context import load_structured_facts

    class FakeStore:
        async def get_row(self, table: str, row_id: str) -> dict[str, object]:
            if table == "applications":
                raise AssertionError("Application was already loaded during access validation")
            return {"id": row_id, "business_name": "Raj Traders"}

        async def list_rows(self, *args: object, **kwargs: object) -> list[dict[str, object]]:
            return []

    monkeypatch.setattr(
        "app.services.rag.application_context.get_document_collection_status",
        lambda *args, **kwargs: asyncio.sleep(0, result={"requirements": []}),
    )
    application = {
        "id": RAJ_APPLICATION_ID,
        "client_id": "client-1",
        "period_label": "May 2026",
    }

    result = await load_structured_facts(
        FakeStore(),  # type: ignore[arg-type]
        application_id=RAJ_APPLICATION_ID,
        question="Which documents are missing?",
        intent="missing_documents",
        application=application,
    )

    assert result["application"]["id"] == RAJ_APPLICATION_ID


@pytest.mark.asyncio
async def test_complete_collection_does_not_load_request_history() -> None:
    """Catches completed checklists paying for application/reminder reads they do not use."""
    from app.services.document_collection import get_document_collection_status

    class FakeStore:
        async def list_rows(
            self, table: str, *args: object, **kwargs: object
        ) -> list[dict[str, object]]:
            if table == "document_requirements":
                return [
                    {
                        "id": "requirement-1",
                        "label": "Sales Register",
                        "requirement_type": "sales_register",
                        "required": True,
                        "status": "received",
                    }
                ]
            raise AssertionError(f"Unexpected completed-collection read: {table}")

        async def get_row(self, table: str, row_id: str) -> dict[str, object]:
            raise AssertionError(f"Unexpected completed-collection read: {table}")

    result = await get_document_collection_status(
        FakeStore(),  # type: ignore[arg-type]
        RAJ_APPLICATION_ID,
    )

    assert result["workflow_status"] == "documents_complete"


@pytest.mark.asyncio
async def test_rag_generation_uses_fast_model_not_heavy_extraction_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches short assistant prose being routed to the heavy extraction model."""
    from app.agents.rag_assistant import RAGAssistant

    observed_model: list[str | None] = []
    observed_max_tokens: list[int | None] = []

    async def complete(*args: object, **kwargs: object) -> dict[str, object]:
        observed_model.append(kwargs.get("model"))
        observed_max_tokens.append(kwargs.get("max_tokens"))
        return {"answer": "Grounded guidance", "confidence": 0.9}

    monkeypatch.setattr("app.agents.rag_assistant.complete_groq_json", complete)
    settings = get_settings().model_copy(
        update={
            "ai_mode": "live",
            "groq_model": "stale-default-model",
            "groq_heavy_model": "heavy-extraction-model",
            "groq_rag_model": "fast-rag-model",
            "rag_max_output_tokens": 420,
        }
    )

    await RAGAssistant(get_store(), settings).generate_grounded_answer(
        {
            "intent": "guidance",
            "question": "Explain the review guidance",
            "application_data": {},
            "application_evidence": [],
            "knowledge_evidence": [{"content": "Grounded source"}],
            "history": [],
        }
    )

    assert observed_model == ["fast-rag-model"]
    assert observed_max_tokens == [420]


def test_rag_model_falls_back_to_known_working_heavy_model() -> None:
    settings = get_settings().model_copy(
        update={
            "groq_model": "stale-default-model",
            "groq_heavy_model": "known-working-model",
            "groq_rag_model": "",
        }
    )

    assert settings.effective_groq_rag_model == "known-working-model"


def test_assistant_model_output_normalizes_provider_confidence_label() -> None:
    from app.schemas.rag import AssistantModelOutput

    output = AssistantModelOutput.model_validate(
        {"answer": "Grounded review guidance", "confidence": "medium"}
    )

    assert output.answer == "Grounded review guidance"
    assert output.confidence == 0.7


@pytest.mark.asyncio
async def test_query_persists_conversation_without_reloading_application_sequentially() -> None:
    """Catches redundant application reads and sequential message inserts on the hot path."""
    from app.agents.rag_assistant import RAGAssistant

    inserted: list[dict[str, object]] = []

    class FakeStore:
        async def list_rows(self, *args: object, **kwargs: object) -> list[dict[str, object]]:
            return []

        async def get_row(self, *args: object, **kwargs: object) -> dict[str, object]:
            raise AssertionError("The graph result already contains the application scope")

        async def insert_row(self, table: str, row: dict[str, object]) -> dict[str, object]:
            await asyncio.sleep(0.08)
            inserted.append(row)
            return row

    class FakeGraph:
        async def ainvoke(self, state: dict[str, object]) -> dict[str, object]:
            return {
                "application_data": {
                    "application": {"demo_session_id": "demo-session-1"}
                },
                "answer": {
                    "answer": "Grounded response",
                    "citations": [],
                    "source_types": ["application"],
                },
            }

    assistant = RAGAssistant(FakeStore(), get_settings())  # type: ignore[arg-type]
    assistant.graph = FakeGraph()
    started = time.perf_counter()

    answer = await assistant.query(
        question="Explain this alert",
        firm_id=DEMO_FIRM_ID,
        application_id=RAJ_APPLICATION_ID,
        user_id="user-1",
        conversation_id="conversation-1",
        source_type=None,
    )

    assert time.perf_counter() - started < 0.14
    assert answer["answer"] == "Grounded response"
    assert [row["role"] for row in inserted] == ["user", "assistant"]
    assert {row["demo_session_id"] for row in inserted} == {"demo-session-1"}
