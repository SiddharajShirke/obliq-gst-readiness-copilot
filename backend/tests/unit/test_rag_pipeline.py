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
        text="# GSTR-2B Matching\n\nCompare supplier GSTIN and invoice number before reviewing possible ITC differences.",
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
