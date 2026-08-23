"""Idempotent first-login workspace bootstrap."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.repositories.base import DataStore


async def bootstrap_user_workspace(
    store: DataStore,
    identity: Mapping[str, Any],
) -> dict[str, Any]:
    rows = await store.rpc(
        "bootstrap_user_workspace",
        {
            "p_user_id": str(identity.get("id") or identity.get("user_id")),
            "p_email": str(identity.get("email") or ""),
            "p_full_name": str(identity.get("full_name") or ""),
        },
    )
    if not rows:
        raise RuntimeError("Workspace bootstrap did not return a workspace")
    return rows[0]
