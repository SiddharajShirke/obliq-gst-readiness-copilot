"""Security helpers for Meta WhatsApp webhook requests."""

from __future__ import annotations

import hashlib
import hmac


def verify_meta_signature(payload: bytes, signature_header: str | None, app_secret: str) -> bool:
    if not signature_header or not app_secret or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), payload, hashlib.sha256).hexdigest()
    supplied = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, supplied)
