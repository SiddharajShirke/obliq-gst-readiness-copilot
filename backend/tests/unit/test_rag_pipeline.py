import pytest

from app.config import get_settings
from app.repositories import get_store
from app.services.rag.embeddings import DeterministicEmbeddingProvider
from app.services.rag.ingestion import ingest_text
from app.services.rag.retrieval import reciprocal_rank_fusion, retrieve_knowledge


def test_deterministic_embeddings_are_384_dimensional_and_normalized() -> None:
    provider = DeterministicEmbeddingProvider(384)
    vector = provider.embed_texts(["purchase register and GSTR-2B reconciliation"])[0]
    assert len(vector) == 384
    magnitude = sum(value * value for value in vector) ** 0.5
    assert magnitude == pytest.approx(1.0)


def test_reciprocal_rank_fusion_prioritizes_item_present_in_both_lists() -> None:
    vector = [
        {"chunk_id": "a", "content": "A", "similarity": 0.9},
        {"chunk_id": "b", "content": "B", "similarity": 0.8},
    ]
    lexical = [
        {"chunk_id": "b", "content": "B", "rank": 0.9},
        {"chunk_id": "c", "content": "C", "rank": 0.8},
    ]

    fused = reciprocal_rank_fusion(vector, lexical)

    assert fused[0]["chunk_id"] == "b"


@pytest.mark.asyncio
async def test_ingested_text_is_retrievable_with_citation_metadata() -> None:
    store = get_store()
    settings = get_settings()
    await ingest_text(
        store,
        settings,
        text=(
            "# GSTR-2B Matching\n\nCompare supplier GSTIN and invoice number before "
            "reviewing possible ITC differences."
        ),
        title="Demo GSTR-2B Guidance",
        source_type="official_gst",
        source_url="https://example.test/gstr2b",
        firm_id=None,
        document_version="demo-v1",
    )

    results = await retrieve_knowledge(
        store,
        settings,
        question="How should supplier invoices be matched with GSTR-2B?",
        firm_id="11111111-1111-1111-1111-111111111111",
    )

    assert results
    assert results[0]["metadata"]["title"] == "Demo GSTR-2B Guidance"


@pytest.mark.asyncio
async def test_application_retrieval_uses_guarded_async_embeddings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RAG queries must share the heavy-work gate instead of blocking inline."""
    from app.services.rag import retrieval

    sync_calls = 0
    async_calls = 0

    def inline_embedding(*args: object, **kwargs: object) -> list[list[float]]:
        nonlocal sync_calls
        sync_calls += 1
        return [[0.0] * 384]

    async def guarded_embedding(*args: object, **kwargs: object) -> list[list[float]]:
        nonlocal async_calls
        async_calls += 1
        return [[0.0] * 384]

    class FakeStore:
        async def rpc(
            self, function_name: str, params: dict[str, object]
        ) -> list[dict[str, object]]:
            return []

    monkeypatch.setattr(retrieval, "embed_texts", inline_embedding, raising=False)
    monkeypatch.setattr(
        retrieval, "embed_texts_async", guarded_embedding, raising=False
    )

    await retrieval.retrieve_application_documents(
        FakeStore(),  # type: ignore[arg-type]
        get_settings(),
        question="Summarize the purchase register",
        firm_id="firm-1",
        application_id="application-1",
    )

    assert async_calls == 1
    assert sync_calls == 0


@pytest.mark.asyncio
async def test_knowledge_ingestion_uses_guarded_async_embeddings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.rag import ingestion

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

    class FakeStore:
        async def list_rows(self, *args: object, **kwargs: object) -> list[dict[str, object]]:
            return []

        async def insert_row(
            self, table: str, row: dict[str, object]
        ) -> dict[str, object]:
            return {"id": f"{table}-1", **row}

        async def update_row(
            self, table: str, row_id: str, row: dict[str, object]
        ) -> dict[str, object]:
            return {"id": row_id, **row}

    monkeypatch.setattr(ingestion, "embed_texts", inline_embedding, raising=False)
    monkeypatch.setattr(
        ingestion, "embed_texts_async", guarded_embedding, raising=False
    )

    await ingestion.ingest_text(
        FakeStore(),  # type: ignore[arg-type]
        get_settings(),
        text="GST reconciliation evidence for CA review.",
        title="GST guidance",
        source_type="official_gst",
        source_url=None,
        firm_id=None,
    )

    assert async_calls == 1
    assert sync_calls == 0
