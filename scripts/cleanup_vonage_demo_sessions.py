#!/usr/bin/env python
"""Expire, anonymize, and remove retained Vonage demo-session data."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings
from app.repositories import get_store
from app.services.whatsapp.cleanup import cleanup_demo_sessions


async def main() -> None:
    result = await cleanup_demo_sessions(get_store(), get_settings())
    print(f"Expired sessions: {result['expired']}")
    print(f"Deleted retained sessions: {result['deleted']}")


if __name__ == "__main__":
    asyncio.run(main())
