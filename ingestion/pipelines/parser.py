"""Document parsing + cleaning (issue #2).

SOURCE FILE -> DOCUMENT PARSER -> TEXT EXTRACTION -> CLEANING
(Master Prompt Section 37, first two stages). Structural analysis and chunking
are #3; metadata enrichment and quality checks are #4.
"""

from __future__ import annotations

import re
from pathlib import Path

import fitz  # PyMuPDF
from docx import Document

SUPPORTED_SUFFIXES = {".pdf", ".docx"}


class UnsupportedDocumentType(ValueError):
    pass


def extract_text_from_pdf(path: Path) -> str:
    """Extract raw text from a PDF via PyMuPDF, page by page."""
    with fitz.open(path) as doc:
        return "\n\n".join(page.get_text() for page in doc)


def extract_text_from_docx(path: Path) -> str:
    """Extract raw text from a .docx via python-docx, paragraph by paragraph."""
    document = Document(path)
    return "\n".join(p.text for p in document.paragraphs)


def extract_text(path: Path) -> str:
    """Dispatch to the right parser by file extension."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    if suffix == ".docx":
        return extract_text_from_docx(path)
    raise UnsupportedDocumentType(
        f"Unsupported document type: {suffix!r} (supported: {sorted(SUPPORTED_SUFFIXES)})"
    )


def clean_text(text: str) -> str:
    """Normalize whitespace/artifacts without altering meaning.

    - normalize line endings
    - rejoin hyphenated words split across a line break ("exam-\\nple" -> "example")
    - collapse runs of horizontal whitespace to a single space
    - collapse 3+ blank lines down to one blank line (preserve paragraph breaks)
    - strip trailing whitespace per line and leading/trailing whitespace overall
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[^\S\n]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_document(path: Path) -> str:
    """Full parse+clean for a single source file (Section 37 stages 1-3)."""
    return clean_text(extract_text(path))
