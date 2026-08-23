from __future__ import annotations

import pytest

from app.config import Settings
from app.repositories.memory import MemoryStore
from app.services.assistant_actions import (
    ActionConflict,
    cancel_action_proposal,
    confirm_action_proposal,
    create_action_proposal,
)

FIRM_ID = "11111111-1111-1111-1111-111111111111"
USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
APPLICATION_ID = "30000000-0000-0000-0000-000000000001"


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore(Settings(app_env="test", use_in_memory_db=True, _env_file=None))


@pytest.mark.asyncio
async def test_reconciliation_action_only_mutates_after_same_ca_confirms(
    store: MemoryStore,
) -> None:
    run = await store.insert_row(
        "reconciliation_runs",
        {"firm_id": FIRM_ID, "application_id": APPLICATION_ID, "status": "completed"},
    )
    item = await store.insert_row(
        "reconciliation_items",
        {
            "reconciliation_run_id": run["id"],
            "match_status": "value_mismatch",
            "review_status": "pending",
            "evidence": {"books": {"invoice_number": "CA/001"}},
        },
    )

    proposal = await create_action_proposal(
        store,
        firm_id=FIRM_ID,
        user_id=USER_ID,
        role="firm_admin",
        application_id=APPLICATION_ID,
        conversation_id="conversation-1",
        action_type="mark_reconciliation_reviewed",
        payload={"item_id": item["id"]},
    )

    assert (await store.get_row("reconciliation_items", item["id"]))["review_status"] == "pending"
    assert proposal["status"] == "pending_confirmation"

    executed = await confirm_action_proposal(
        store,
        Settings(app_env="test", ai_mode="mock", use_in_memory_db=True, _env_file=None),
        proposal_id=proposal["id"],
        firm_id=FIRM_ID,
        user_id=USER_ID,
        role="firm_admin",
        conversation_id="conversation-1",
    )

    assert executed["status"] == "executed"
    assert (await store.get_row("reconciliation_items", item["id"]))["review_status"] == "reviewed"


@pytest.mark.asyncio
async def test_cancelled_action_never_mutates_and_cannot_be_confirmed(
    store: MemoryStore,
) -> None:
    finding = await store.insert_row(
        "validation_findings",
        {
            "firm_id": FIRM_ID,
            "application_id": APPLICATION_ID,
            "finding_type": "period_mismatch",
            "severity": "medium",
            "message": "Review period",
            "status": "open",
        },
    )
    proposal = await create_action_proposal(
        store,
        firm_id=FIRM_ID,
        user_id=USER_ID,
        role="reviewer",
        application_id=APPLICATION_ID,
        conversation_id="conversation-2",
        action_type="mark_validation_reviewed",
        payload={"finding_id": finding["id"]},
    )

    cancelled = await cancel_action_proposal(
        store,
        proposal_id=proposal["id"],
        firm_id=FIRM_ID,
        user_id=USER_ID,
        conversation_id="conversation-2",
    )

    assert cancelled["status"] == "cancelled"
    assert (await store.get_row("validation_findings", finding["id"]))["status"] == "open"
    with pytest.raises(ActionConflict):
        await confirm_action_proposal(
            store,
            Settings(app_env="test", ai_mode="mock", use_in_memory_db=True, _env_file=None),
            proposal_id=proposal["id"],
            firm_id=FIRM_ID,
            user_id=USER_ID,
            role="reviewer",
            conversation_id="conversation-2",
        )


@pytest.mark.asyncio
async def test_proposal_rejects_cross_application_target_and_preparer_mutation(
    store: MemoryStore,
) -> None:
    finding = await store.insert_row(
        "validation_findings",
        {
            "firm_id": FIRM_ID,
            "application_id": "other-application",
            "finding_type": "period_mismatch",
            "severity": "medium",
            "message": "Private",
            "status": "open",
        },
    )

    with pytest.raises(LookupError):
        await create_action_proposal(
            store,
            firm_id=FIRM_ID,
            user_id=USER_ID,
            role="reviewer",
            application_id=APPLICATION_ID,
            conversation_id="conversation-3",
            action_type="mark_validation_reviewed",
            payload={"finding_id": finding["id"]},
        )
    with pytest.raises(PermissionError):
        await create_action_proposal(
            store,
            firm_id=FIRM_ID,
            user_id=USER_ID,
            role="gst_preparer",
            application_id=APPLICATION_ID,
            conversation_id="conversation-3",
            action_type="mark_reconciliation_reviewed",
            payload={"item_id": "unknown"},
        )
