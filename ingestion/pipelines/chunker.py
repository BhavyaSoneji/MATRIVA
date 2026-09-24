"""Semantic chunking (issue #3).

Chunks a parsed KnowledgeDocument (#2's output) into KnowledgeChunk records,
300-700 tokens each, per Master Prompt Section 14. Never splits blindly by
character count: paragraph blocks are the atomic unit, and a heading is always
kept attached to the paragraph(s) that follow it rather than left as a
dangling final line in a chunk.

Token count here is an approximation (whitespace word count), not a real LLM
tokenizer -- good enough for sizing chunks without adding a tokenizer
dependency at this stage. If a future issue needs exact token counts (e.g. to
fit an LLM context window precisely), swap `_count_tokens` for a real one.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# ingestion/ and backend/ are separate top-level packages with no shared
# packaging/install step yet -- bootstrap backend onto sys.path so the
# canonical schema from #1 can be reused here instead of duplicated.
_BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.schemas.knowledge import KnowledgeChunk, KnowledgeDocument  # noqa: E402

MIN_TOKENS = 300
MAX_TOKENS = 700

_HEADING_RE = re.compile(r"^[^\n.!?]{1,80}$")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _count_tokens(text: str) -> int:
    return len(text.split())


def _is_heading(block: str) -> bool:
    """Single short line, no terminal punctuation -- a common heading shape
    once headings have been flattened to plain text by the parser (#2)."""
    return "\n" not in block and bool(_HEADING_RE.match(block.strip()))


def _split_oversized_block(block: str, max_tokens: int) -> list[str]:
    """A single paragraph that alone exceeds max_tokens: split at sentence
    boundaries (never mid-sentence) so the split still respects structure."""
    sentences = _SENTENCE_SPLIT_RE.split(block)
    parts: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for sentence in sentences:
        sentence_tokens = _count_tokens(sentence)
        if current and current_tokens + sentence_tokens > max_tokens:
            parts.append(" ".join(current))
            current, current_tokens = [], 0
        current.append(sentence)
        current_tokens += sentence_tokens
    if current:
        parts.append(" ".join(current))
    return parts


def _group_blocks(
    blocks: list[str], min_tokens: int, max_tokens: int
) -> list[str]:
    """Group paragraph blocks into chunk-sized text groups, keeping any
    heading attached to the block(s) immediately following it."""
    groups: list[str] = []
    buffer: list[str] = []
    buffer_tokens = 0
    pending_heading: str | None = None

    def flush() -> None:
        nonlocal buffer, buffer_tokens
        if buffer:
            groups.append("\n\n".join(buffer))
            buffer, buffer_tokens = [], 0

    for block in blocks:
        if _is_heading(block):
            # A heading never ends a chunk on its own -- hold it until the
            # next real content block arrives.
            if buffer_tokens >= min_tokens:
                flush()
            pending_heading = block
            continue

        pieces = (
            _split_oversized_block(block, max_tokens)
            if _count_tokens(block) > max_tokens
            else [block]
        )
        for piece in pieces:
            piece_tokens = _count_tokens(piece)
            heading_tokens = _count_tokens(pending_heading) if pending_heading else 0
            if buffer and buffer_tokens + heading_tokens + piece_tokens > max_tokens:
                flush()
            if pending_heading:
                buffer.append(pending_heading)
                buffer_tokens += heading_tokens
                pending_heading = None
            buffer.append(piece)
            buffer_tokens += piece_tokens
            if buffer_tokens >= min_tokens:
                flush()

    if pending_heading and not buffer:
        buffer.append(pending_heading)
    flush()
    return groups


def chunk_document(
    document: KnowledgeDocument,
    *,
    min_tokens: int = MIN_TOKENS,
    max_tokens: int = MAX_TOKENS,
) -> list[KnowledgeChunk]:
    """Chunk document.content (already parsed+cleaned by #2) into KnowledgeChunks,
    inheriting the parent document's metadata (Section 14's required fields)."""
    blocks = [b for b in document.content.split("\n\n") if b.strip()]
    groups = _group_blocks(blocks, min_tokens, max_tokens)

    return [
        KnowledgeChunk(
            chunk_id=f"{document.document_id}-chunk-{index:04d}",
            document_id=document.document_id,
            source_id=document.source_id,
            domain=document.domain,
            topic=document.topic,
            pregnancy_stage=document.pregnancy_stage,
            evidence_level=document.evidence_level,
            region=document.region,
            language=document.language,
            content=group,
            chunk_index=index,
            token_count=_count_tokens(group),
        )
        for index, group in enumerate(groups)
    ]
