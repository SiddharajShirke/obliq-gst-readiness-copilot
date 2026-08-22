import hashlib
import hmac
from datetime import UTC, datetime, timedelta

from app.services.upload_tokens import issue_upload_token, verify_upload_token


def test_upload_token_round_trip_and_expiration() -> None:
    now = datetime(2026, 8, 18, tzinfo=UTC)
    raw, record = issue_upload_token(
        firm_id="firm-1",
        application_id="app-1",
        client_id="client-1",
        demo_session_id="session-1",
        pepper="pepper",
        ttl=timedelta(hours=1),
        now=now,
    )

    verified = verify_upload_token(raw, record, pepper="pepper", now=now + timedelta(minutes=5))
    assert verified.firm_id == "firm-1"
    assert verified.application_id == "app-1"
    assert verified.demo_session_id == "session-1"

    assert verify_upload_token(
        raw,
        record,
        pepper="pepper",
        now=now + timedelta(hours=2),
    ) is None


def test_upload_token_hash_is_domain_separated_hmac_sha256() -> None:
    expected = hmac.new(
        b"pepper",
        b"upload:fixed-token",
        hashlib.sha256,
    ).hexdigest()

    from app.services.upload_tokens import hash_upload_token

    assert hash_upload_token("fixed-token", "pepper") == expected


def test_revoked_upload_token_is_rejected() -> None:
    now = datetime(2026, 8, 22, tzinfo=UTC)
    raw, record = issue_upload_token(
        firm_id="firm-1",
        application_id="app-1",
        client_id="client-1",
        demo_session_id=None,
        requirement_id="requirement-1",
        pepper="pepper",
        ttl=timedelta(hours=1),
        now=now,
    )
    revoked = record.__class__(
        firm_id=record.firm_id,
        application_id=record.application_id,
        client_id=record.client_id,
        demo_session_id=record.demo_session_id,
        requirement_id=record.requirement_id,
        token_hash=record.token_hash,
        expires_at=record.expires_at,
        revoked_at=now,
    )

    assert verify_upload_token(raw, revoked, pepper="pepper", now=now) is None
