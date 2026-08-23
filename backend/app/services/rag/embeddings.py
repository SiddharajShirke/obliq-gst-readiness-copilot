"""Embedding provider abstraction with a free deterministic demo implementation."""

from __future__ import annotations

import asyncio
import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

from app.config import Settings


class EmbeddingProvider(Protocol):
    dimension: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class DeterministicEmbeddingProvider:
    """Feature-hashing embeddings for tests and hosted demo mode.

    They are not intended to replace semantic embeddings in live mode, but preserve the
    complete pgvector ingestion/retrieval shape without downloading a model.
    """

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimension
            tokens = re.findall(r"[a-z0-9]+", text.lower())
            for token in tokens:
                digest = hashlib.sha256(token.encode()).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimension
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vector[index] += sign
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors


class SentenceTransformerEmbeddingProvider:
    def __init__(self, model_name: str, dimension: int = 384) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.dimension = dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        output = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        vectors = [list(map(float, row)) for row in output]
        for vector in vectors:
            if len(vector) != self.dimension:
                raise ValueError(
                    f"Embedding model returned {len(vector)} dimensions; expected {self.dimension}"
                )
        return vectors


@lru_cache(maxsize=4)
def _cached_provider(mode: str, model_name: str, dimension: int) -> EmbeddingProvider:
    if mode == "deterministic":
        return DeterministicEmbeddingProvider(dimension)
    return SentenceTransformerEmbeddingProvider(model_name, dimension)


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    mode = (
        "deterministic"
        if settings.ai_mode == "mock" or settings.embedding_provider == "mock"
        else "local"
    )
    return _cached_provider(mode, settings.embedding_model, settings.embedding_dimension)


def embed_texts(texts: list[str], settings: Settings) -> list[list[float]]:
    return get_embedding_provider(settings).embed_texts(texts)


async def warm_embedding_provider(settings: Settings) -> None:
    """Load and exercise the configured embedder before requests are accepted."""
    provider = await asyncio.to_thread(get_embedding_provider, settings)
    await asyncio.to_thread(provider.embed_texts, ["OBLIQ embedding warmup"])
