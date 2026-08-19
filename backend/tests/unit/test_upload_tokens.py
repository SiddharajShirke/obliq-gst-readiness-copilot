from datetime import UTC, datetime, timedelta

from app.services.upload_tokens import issue_upload_token, verify_upload_token


def test_upload_token_round_trip_and_expiration() -> None:
    now = datetime(2026, 8, 18, tzinfo=UTC)
    raw, record = issue_upload_token(
        application_id="app-1",
        client_id="client-1",
        pepper="pepper",
        ttl=timedelta(hours=1),
        now=now,
    )

    verified = verify_upload_token(raw, record, pepper="pepper", now=now + timedelta(minutes=5))
    assert verified.application_id == "app-1"

    assert verify_upload_token(
        raw,
        record,
        pepper="pepper",
        now=now + timedelta(hours=2),
    ) is None
