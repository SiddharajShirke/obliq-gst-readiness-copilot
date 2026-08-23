"""Knowledge document text extraction."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


@dataclass(slots=True)
class ExtractedKnowledge:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def extract_knowledge_bytes(content: bytes, filename: str) -> ExtractedKnowledge:
    extension = Path(filename).suffix.lower()
    if extension in {".txt", ".md"}:
        return ExtractedKnowledge(content.decode("utf-8", errors="ignore"))
    if extension in {".html", ".htm"}:
        soup = BeautifulSoup(content, "html.parser")
        return ExtractedKnowledge(soup.get_text("\n", strip=True))
    if extension == ".pdf":
        import fitz

        pages: list[str] = []
        with fitz.open(stream=content, filetype="pdf") as document:
            for page_number, page in enumerate(document, start=1):
                page_text = page.get_text("text").strip()
                if page_text:
                    pages.append(f"## Page {page_number}\n\n{page_text}")
        return ExtractedKnowledge("\n\n".join(pages), {"page_count": len(pages)})
    if extension == ".docx":
        from docx import Document

        document = Document(io.BytesIO(content))
        paragraphs = [
            paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()
        ]
        return ExtractedKnowledge("\n\n".join(paragraphs))
    raise ValueError(f"Unsupported knowledge file type: {extension}")
