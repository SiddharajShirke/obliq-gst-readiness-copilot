"""Heading-aware text chunking used by the RAG ingestion pipeline."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class KnowledgeChunk:
    index: int
    content: str
    heading: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _heading_and_body(text: str) -> tuple[str | None, str]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            return heading or None, "\n".join(lines[index + 1 :]).strip()
    return None, text


def _tail_by_chars(text: str, target: int) -> str:
    if len(text) <= target:
        return text
    tail = text[-target:]
    first_space = tail.find(" ")
    return tail[first_space + 1 :] if first_space >= 0 else tail


def chunk_document(
    text: str,
    sections: list[dict[str, Any]] | None = None,
    *,
    max_chars: int = 900,
    overlap_chars: int = 140,
) -> list[KnowledgeChunk]:
    if max_chars <= overlap_chars or max_chars < 80:
        raise ValueError("max_chars must be larger than overlap_chars and at least 80")

    cleaned = _clean_text(text)
    if not cleaned:
        return []

    heading, body = _heading_and_body(cleaned)
    heading_prefix = f"{heading}\n\n" if heading else ""
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", body) if item.strip()]
    words: list[str] = []
    for paragraph in paragraphs or [body]:
        words.extend(paragraph.split())

    chunks: list[KnowledgeChunk] = []
    current = ""
    previous_payload = ""
    chunk_index = 0

    for word in words:
        candidate = f"{current} {word}".strip()
        payload_limit = max_chars - len(heading_prefix)
        if current and len(candidate) > payload_limit:
            content = f"{heading_prefix}{current}".strip()
            chunks.append(KnowledgeChunk(chunk_index, content, heading, {"section": heading}))
            chunk_index += 1
            previous_payload = current
            current = f"{_tail_by_chars(previous_payload, overlap_chars)} {word}".strip()
        else:
            current = candidate

    if current:
        chunks.append(
            KnowledgeChunk(
                chunk_index, f"{heading_prefix}{current}".strip(), heading, {"section": heading}
            )
        )

    return [chunk for chunk in chunks if len(chunk.content) >= 20]
