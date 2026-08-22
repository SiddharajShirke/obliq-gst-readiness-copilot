from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.services.document_processing.ingestion import (
    ArchiveValidationError,
    classify_for_ingestion,
    read_safe_zip,
)


def _zip(entries: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return output.getvalue()


def test_explicit_slot_wins_over_filename() -> None:
    result = classify_for_ingestion(
        filename="unclear.pdf",
        mime_type="application/pdf",
        content=b"%PDF-1.4",
        explicit_category="credit_debit_notes",
    )
    assert result.document_type == "credit_debit_notes"
    assert result.source == "explicit_slot"


def test_ambiguous_pdf_is_unknown_not_purchase_invoice() -> None:
    result = classify_for_ingestion(
        filename="scan_001.pdf",
        mime_type="application/pdf",
        content=b"%PDF-1.4 unrelated",
    )
    assert result.document_type == "unknown"
    assert result.source == "unresolved"


def test_safe_zip_returns_supported_files_once() -> None:
    entries = read_safe_zip(
        _zip(
            {
                "dataset/01_Sales_Register.csv": b"Invoice No,Taxable Value\nS-1,100",
                "dataset/readme.txt": b"ignored",
            }
        ),
        allowed_extensions={"csv", "pdf"},
        max_files=10,
        max_total_bytes=1024,
    )
    assert [(entry.name, entry.content) for entry in entries] == [
        ("01_Sales_Register.csv", b"Invoice No,Taxable Value\nS-1,100")
    ]


@pytest.mark.parametrize("name", ["../secret.pdf", "/absolute.pdf", "C:/escape.pdf"])
def test_zip_path_traversal_is_rejected(name: str) -> None:
    with pytest.raises(ArchiveValidationError, match="unsafe path"):
        read_safe_zip(
            _zip({name: b"%PDF-1.4"}),
            allowed_extensions={"pdf"},
            max_files=10,
            max_total_bytes=1024,
        )


def test_zip_size_and_count_guards_are_enforced() -> None:
    with pytest.raises(ArchiveValidationError, match="too many"):
        read_safe_zip(
            _zip({"a.pdf": b"a", "b.pdf": b"b"}),
            allowed_extensions={"pdf"},
            max_files=1,
            max_total_bytes=1024,
        )
    with pytest.raises(ArchiveValidationError, match="too large"):
        read_safe_zip(
            _zip({"a.pdf": b"12345"}),
            allowed_extensions={"pdf"},
            max_files=10,
            max_total_bytes=4,
        )
