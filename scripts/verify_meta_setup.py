#!/usr/bin/env python3
"""Send one real test message with the configured Meta Cloud API provider."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import Settings  # noqa: E402
from app.services.whatsapp.factory import get_whatsapp_provider, load_meta_credentials  # noqa: E402


async def main() -> None:
    settings = Settings(whatsapp_provider="meta")
    credentials = load_meta_credentials(settings)
    if not credentials.test_recipient_number:
        raise SystemExit("META_TEST_RECIPIENT_NUMBER or local credentials are required")
    provider = get_whatsapp_provider(settings)
    result = await provider.send_text(
        recipient=credentials.test_recipient_number,
        text="OBLIQ local Meta WhatsApp integration is connected.",
    )
    print(f"provider={provider.name} status={result.status} message_id={result.external_message_id}")


if __name__ == "__main__":
    asyncio.run(main())
