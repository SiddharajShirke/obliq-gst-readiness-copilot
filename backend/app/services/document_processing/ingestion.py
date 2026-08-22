"""Shared classification and archive intake primitives for every upload mode."""

from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from app.services.document_processing.taxonomy import (
    ALL_DOCUMENT_TYPES,
    CLIENT_REQUIREMENTS,
    classify_known_filename,
)


class ArchiveValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    document_type: str
    source: str


@dataclass(frozen=True, slots=True)
class ArchiveEntry:
    name: str
    content: bytes


def _content_classification(content: bytes) -> str | None:
    sample = content[:32768].decode("utf-8", errors="ignore").lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", sample)
    if "supplier gstin" in normalized and "itc" in normalized and "gstr 2b" in normalized:
        return "gstr2b"
    if "credit note" in normalized or "debit note" in normalized:
        return "credit_debit_notes"
    if "reverse charge" in normalized or "rcm flag" in normalized:
        return "gst_special_transactions"
    if "customer gstin" in normalized and "sales" in normalized:
        return "sales_register"
    if "supplier gstin" in normalized and "purchase" in normalized:
        return "purchase_register"
    return None


def classify_for_ingestion(
    *,
    filename: str,
    mime_type: str,
    content: bytes,
    explicit_category: str | None = None,
) -> ClassificationResult:
    del mime_type
    if explicit_category:
        if explicit_category not in CLIENT_REQUIREMENTS:
            raise ValueError("Unknown explicit document category")
        return ClassificationResult(explicit_category, "explicit_slot")
    known = classify_known_filename(filename)
    if known:
        return ClassificationResult(known, "filename")
    content_type = _content_classification(content)
    if content_type:
        return ClassificationResult(content_type, "content_rule")
    return ClassificationResult("unknown", "unresolved")


def _unsafe_archive_name(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return path.is_absolute() or ".." in path.parts or bool(re.match(r"^[a-zA-Z]:", normalized))


def read_safe_zip(
    content: bytes,
    *,
    allowed_extensions: set[str],
    max_files: int,
    max_total_bytes: int,
) -> list[ArchiveEntry]:
    try:
        archive = ZipFile(BytesIO(content))
    except BadZipFile as exc:
        raise ArchiveValidationError("Invalid ZIP archive") from exc
    with archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        if any(_unsafe_archive_name(member.filename) for member in members):
            raise ArchiveValidationError("ZIP contains an unsafe path")
        supported = [
            member
            for member in members
            if Path(member.filename).suffix.lower().lstrip(".") in allowed_extensions
        ]
        if len(supported) > max_files:
            raise ArchiveValidationError("ZIP contains too many supported files")
        if sum(member.file_size for member in supported) > max_total_bytes:
            raise ArchiveValidationError("ZIP expanded content is too large")
        entries: list[ArchiveEntry] = []
        for member in supported:
            data = archive.read(member)
            if len(data) != member.file_size:
                raise ArchiveValidationError("ZIP member size mismatch")
            entries.append(ArchiveEntry(Path(member.filename).name, data))
        return entries


def is_business_document_type(document_type: str) -> bool:
    return document_type in ALL_DOCUMENT_TYPES and document_type not in {
        "developer_ground_truth",
        "unknown",
    }
