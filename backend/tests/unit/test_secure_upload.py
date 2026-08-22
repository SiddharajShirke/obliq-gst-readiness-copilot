from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.config import Settings
from app.services.secure_upload import (
    SecureUploadValidationError,
    build_storage_path,
    validate_secure_upload,
)


def _settings(**overrides) -> Settings:
    return Settings(
        app_env="test",
        whatsapp_provider="mock",
        allowed_upload_extensions="pdf,png,jpg,jpeg,csv,xlsx,docx,json",
        max_upload_mb=1,
        upload_token_pepper="upload-pepper",
        _env_file=None,
        **overrides,
    )


def _office_zip(folder: str) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(f"{folder}/document.xml", "<document/>")
    return output.getvalue()


@pytest.mark.parametrize(
    ("filename", "mime_type", "content"),
    [
        ("return.pdf", "application/pdf", b"%PDF-1.7\nsynthetic"),
        ("photo.jpg", "image/jpeg", b"\xff\xd8\xff\xe0synthetic"),
        ("scan.png", "image/png", b"\x89PNG\r\n\x1a\nsynthetic"),
        ("register.csv", "text/csv", b"invoice,total\nA-1,100\n"),
        ("data.json", "application/json", b'{"invoice": "A-1"}'),
        (
            "register.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            _office_zip("xl"),
        ),
        (
            "letter.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            _office_zip("word"),
        ),
    ],
)
def test_supported_files_are_validated_without_processing(
    filename: str,
    mime_type: str,
    content: bytes,
) -> None:
    validated = validate_secure_upload(
        _settings(),
        filename=filename,
        declared_mime_type=mime_type,
        content=content,
    )

    assert validated.original_name == filename
    assert validated.mime_type == mime_type
    assert validated.file_size == len(content)
    assert len(validated.sha256) == 64


@pytest.mark.parametrize(
    ("filename", "mime_type", "content", "code"),
    [
        ("empty.pdf", "application/pdf", b"", "empty"),
        ("program.exe", "application/octet-stream", b"MZ", "unsupported"),
        ("invoice.pdf", "image/png", b"%PDF-1.7\n", "mime_mismatch"),
        ("invoice.pdf", "application/pdf", b"not a pdf", "signature_mismatch"),
        ("program.csv", "text/csv", b"MZfake executable", "signature_mismatch"),
        (
            "register.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            b"PKbroken",
            "signature_mismatch",
        ),
        ("data.json", "application/json", b"{broken", "signature_mismatch"),
    ],
)
def test_invalid_file_content_is_rejected_before_storage(
    filename: str,
    mime_type: str,
    content: bytes,
    code: str,
) -> None:
    with pytest.raises(SecureUploadValidationError) as raised:
        validate_secure_upload(
            _settings(),
            filename=filename,
            declared_mime_type=mime_type,
            content=content,
        )

    assert raised.value.code == code


def test_oversized_file_is_rejected() -> None:
    with pytest.raises(SecureUploadValidationError) as raised:
        validate_secure_upload(
            _settings(),
            filename="large.pdf",
            declared_mime_type="application/pdf",
            content=b"%PDF" + (b"x" * (1024 * 1024)),
        )

    assert raised.value.code == "oversized"


def test_filename_and_storage_paths_cannot_escape_the_token_scope() -> None:
    validated = validate_secure_upload(
        _settings(),
        filename="../unsafe GST statement?.pdf",
        declared_mime_type="application/pdf",
        content=b"%PDF-1.7\nsynthetic",
    )
    assert validated.safe_name == "unsafe_GST_statement_.pdf"

    normal = build_storage_path(
        firm_id="firm-1",
        client_id="client-1",
        application_id="app-1",
        demo_session_id=None,
        document_id="document-1",
        safe_name=validated.safe_name,
    )
    demo = build_storage_path(
        firm_id="firm-1",
        client_id="client-1",
        application_id="clone-1",
        demo_session_id="session-1",
        document_id="document-1",
        safe_name=validated.safe_name,
    )

    assert normal == "firm-1/client-1/app-1/document-1/unsafe_GST_statement_.pdf"
    assert demo == (
        "firm-1/client-1/session-1/clone-1/document-1/unsafe_GST_statement_.pdf"
    )
