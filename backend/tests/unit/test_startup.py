from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import app.main as main_module


@pytest.mark.asyncio
async def test_application_startup_does_not_wait_for_embedding_warmup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A slow local embedder must not prevent Uvicorn from binding Render's port."""
    warmup_started = asyncio.Event()
    release_warmup = asyncio.Event()
    lifespan_entered = asyncio.Event()
    release_lifespan = asyncio.Event()

    async def blocked_warmup(_: object) -> None:
        warmup_started.set()
        await release_warmup.wait()

    monkeypatch.setattr(
        main_module,
        "settings",
        SimpleNamespace(
            app_env="production",
            use_in_memory_db=False,
            whatsapp_provider="vonage",
            ai_mode="live",
            embedding_provider="local",
        ),
    )
    monkeypatch.setattr(main_module, "warm_embedding_provider", blocked_warmup)

    async def run_lifespan() -> None:
        async with main_module.lifespan(main_module.app):
            lifespan_entered.set()
            await release_lifespan.wait()

    lifespan_task = asyncio.create_task(run_lifespan())
    await asyncio.wait_for(warmup_started.wait(), timeout=1)

    try:
        await asyncio.wait_for(lifespan_entered.wait(), timeout=0.25)
    finally:
        release_warmup.set()
        release_lifespan.set()
        await lifespan_task

