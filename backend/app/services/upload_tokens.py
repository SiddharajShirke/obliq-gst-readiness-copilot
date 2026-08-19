"""Creation and validation of public upload tokens."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class UploadTokenRecord:
    application_id: str
    client_id: str
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None = None


def hash_upload_token(raw_token: str, pepper: str) -> str:
    return hashlib.sha256(f"{pepper}:{raw_token}".encode()).hexdigest()


def issue_upload_token(
    *,
    application_id: str,
    client_id: str,
    pepper: str,
    ttl: timedelta,
    now: datetime | None = None,
) -> tuple[str, UploadTokenRecord]:
    now = now or datetime.now(UTC)
    raw_token = secrets.token_urlsafe(32)
    return raw_token, UploadTokenRecord(
        application_id=application_id,
        client_id=client_id,
        token_hash=hash_upload_token(raw_token, pepper),
        expires_at=now + ttl,
    )


def verify_upload_token(
    raw_token: str,
    record: UploadTokenRecord,
    *,
    pepper: str,
    now: datetime | None = None,
) -> UploadTokenRecord | None:
    now = now or datetime.now(UTC)
    if record.revoked_at is not None or record.expires_at <= now:
        return None
    candidate = hash_upload_token(raw_token, pepper)
    if not secrets.compare_digest(candidate, record.token_hash):
        return None
    return record
