import logging

from app.middleware import UploadTokenRedactionFilter, redact_upload_token_path


def test_upload_tokens_are_redacted_from_application_and_access_log_paths() -> None:
    token = "A" * 43
    path = f"/api/v1/public/upload/{token}/status?poll=1"

    assert redact_upload_token_path(path) == (
        "/api/v1/public/upload/[REDACTED]/status?poll=1"
    )

    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:1", "GET", path, "1.1", 200),
        None,
    )
    assert UploadTokenRedactionFilter().filter(record)
    assert token not in str(record.args)
    assert "[REDACTED]" in str(record.args)
