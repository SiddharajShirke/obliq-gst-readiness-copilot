#!/usr/bin/env python3
"""Ingest demo knowledge files into configured Supabase pgvector storage."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import Settings  # noqa: E402
from app.repositories.memory import DEMO_FIRM_ID  # noqa: E402
from app.repositories.supabase import SupabaseStore  # noqa: E402
from app.services.rag.ingestion import ingest_file  # noqa: E402


async def main() -> None:
    settings = Settings()
    if settings.use_in_memory_db:
        print("The in-memory backend already seeds three demo knowledge chunks on startup.")
        print("Use USE_IN_MEMORY_DB=false to persist these files in Supabase pgvector.")
        return
    store = SupabaseStore(settings)
    for path in sorted((ROOT / "demo_data" / "knowledge").glob("*.md")):
        official = path.name.startswith("gstr2b")
        result = await ingest_file(
            store,
            settings,
            path,
            source_type="official_gst" if official else "firm_sop",
            source_url="https://tutorial.gst.gov.in/userguide/returns/Manual_gstr2b.htm" if official else None,
            firm_id=None if official else DEMO_FIRM_ID,
        )
        print(f"{path.name}: {result.get('chunk_count', 0)} chunks; skipped={result.get('skipped', False)}")


if __name__ == "__main__":
    asyncio.run(main())
