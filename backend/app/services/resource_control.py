"""Small in-process guard for memory-heavy prototype operations."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from threading import BoundedSemaphore


class HeavyProcessingGate:
    """Serialize heavy work without blocking the FastAPI event loop."""

    def __init__(self, concurrency: int) -> None:
        self._semaphore = BoundedSemaphore(concurrency)

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        await asyncio.to_thread(self._semaphore.acquire)
        try:
            yield
        finally:
            self._semaphore.release()


@lru_cache(maxsize=4)
def heavy_processing_gate(concurrency: int) -> HeavyProcessingGate:
    return HeavyProcessingGate(concurrency)
