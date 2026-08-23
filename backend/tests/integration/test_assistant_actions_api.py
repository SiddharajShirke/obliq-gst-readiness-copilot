from __future__ import annotations

import asyncio
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.repositories import get_store

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}
FIRM_ID = "11111111-1111-1111-1111-111111111111"
APPLICATION_ID = "30000000-0000-0000-0000-000000000001"


def test_action_question_requires_confirmation_then_executes_once() -> None:
    store = get_store()
    run = asyncio.run(
        store.insert_row(
            "reconciliation_runs",
            {"firm_id": FIRM_ID, "application_id": APPLICATION_ID, "status": "completed"},
        )
    )
    item = asyncio.run(
        store.insert_row(
            "reconciliation_items",
            {
                "reconciliation_run_id": run["id"],
                "match_status": "value_mismatch",
                "review_status": "pending",
                "evidence": {"books": {"invoice_number": "ACTION/001"}},
            },
        )
    )
    conversation_id = str(uuid.uuid4())

    proposed = client.post(
        "/api/v1/assistant/query",
        headers=AUTH,
        json={
            "application_id": APPLICATION_ID,
            "conversation_id": conversation_id,
            "question": f"Mark reconciliation item {item['id']} as reviewed",
        },
    )

    assert proposed.status_code == 200, proposed.text
    preview = proposed.json()["proposed_action"]
    assert preview["status"] == "pending_confirmation"
    assert preview["action_type"] == "mark_reconciliation_reviewed"
    assert asyncio.run(store.get_row("reconciliation_items", item["id"]))[
        "review_status"
    ] == "pending"

    confirmed = client.post(
        f"/api/v1/assistant/actions/{preview['id']}/confirm",
        headers=AUTH,
        json={"conversation_id": conversation_id},
    )

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "executed"
    assert asyncio.run(store.get_row("reconciliation_items", item["id"]))[
        "review_status"
    ] == "reviewed"
    duplicate = client.post(
        f"/api/v1/assistant/actions/{preview['id']}/confirm",
        headers=AUTH,
        json={"conversation_id": conversation_id},
    )
    assert duplicate.status_code == 409


def test_action_proposal_can_be_cancelled_without_mutation() -> None:
    store = get_store()
    finding = asyncio.run(
        store.insert_row(
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
    )
    conversation_id = str(uuid.uuid4())
    # The API action planner currently exposes reconciliation review; create the same
    # persisted guardrail directly to exercise the public cancellation contract.
    from app.services.assistant_actions import create_action_proposal

    proposal = asyncio.run(
        create_action_proposal(
            store,
            firm_id=FIRM_ID,
            user_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            role="firm_admin",
            application_id=APPLICATION_ID,
            conversation_id=conversation_id,
            action_type="mark_validation_reviewed",
            payload={"finding_id": finding["id"]},
        )
    )

    cancelled = client.post(
        f"/api/v1/assistant/actions/{proposal['id']}/cancel",
        headers=AUTH,
        json={"conversation_id": conversation_id},
    )

    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert asyncio.run(store.get_row("validation_findings", finding["id"]))["status"] == "open"
