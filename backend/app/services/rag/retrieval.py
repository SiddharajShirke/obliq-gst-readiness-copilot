"""Hybrid vector/lexical retrieval with reciprocal-rank fusion."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.config import Settings
from app.repositories.base import DataStore
from app.services.rag.embeddings import embed_texts


def reciprocal_rank_fusion(
    vector_results: list[dict[str, Any]],
    lexical_results: list[dict[str, Any]],
    *,
    k: int = 60,
) -> list[dict[str, Any]]:
    combined: dict[str, dict[str, Any]] = {}
    for result_set, channel in ((vector_results, "vector"), (lexical_results, "lexical")):
        for rank, row in enumerate(result_set, start=1):
            chunk_id = str(row["chunk_id"])
            target = combined.setdefault(
                chunk_id,
                {**deepcopy(row), "rrf_score": 0.0, "channels": []},
            )
            target["rrf_score"] += 1 / (k + rank)
            target["channels"].append(channel)
            if channel == "vector":
                target["similarity"] = row.get("similarity")
            else:
                target["lexical_rank"] = row.get("rank")
    return sorted(combined.values(), key=lambda row: row["rrf_score"], reverse=True)


async def retrieve_knowledge(
    store: DataStore,
    settings: Settings,
    *,
    question: str,
    firm_id: str,
    source_type: str | None = None,
) -> list[dict[str, Any]]:
    query_embedding = embed_texts([question], settings)[0]
    vector_results = await store.rpc(
        "match_knowledge_chunks",
        {
            "query_embedding": query_embedding,
            "user_firm_id": firm_id,
            "filter_source_type": source_type,
            "match_count": settings.rag_vector_top_k,
            "min_similarity": settings.rag_min_similarity,
        },
    )
    lexical_results = await store.rpc(
        "search_knowledge_chunks_lexical",
        {
            "query_text": question,
            "user_firm_id": firm_id,
            "filter_source_type": source_type,
            "match_count": settings.rag_vector_top_k,
        },
    )
    return reciprocal_rank_fusion(vector_results, lexical_results)[: settings.rag_final_top_k]


async def retrieve_application_documents(
    store: DataStore,
    settings: Settings,
    *,
    question: str,
    firm_id: str,
    application_id: str,
) -> list[dict[str, Any]]:
    query_embedding = embed_texts([question], settings)[0]
    rows = await store.rpc(
        "match_application_document_chunks",
        {
            "query_embedding": query_embedding,
            "user_firm_id": firm_id,
            "target_application_id": application_id,
            "match_count": settings.rag_vector_top_k,
            "min_similarity": settings.rag_min_similarity,
        },
    )
    return rows[: settings.rag_final_top_k]
