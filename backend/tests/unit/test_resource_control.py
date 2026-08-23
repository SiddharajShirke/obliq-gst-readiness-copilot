import asyncio

import pytest

from app.services.resource_control import HeavyProcessingGate


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_leak_the_heavy_processing_slot() -> None:
    gate = HeavyProcessingGate(1)

    async with gate.slot():
        waiter = asyncio.create_task(_enter_gate(gate))
        await asyncio.sleep(0.01)
        waiter.cancel()

    with pytest.raises(asyncio.CancelledError):
        await waiter
    await asyncio.wait_for(_enter_gate(gate), timeout=0.25)


async def _enter_gate(gate: HeavyProcessingGate) -> None:
    async with gate.slot():
        return
