from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.security import sanitize_filename, sha256_bytes
from app.models import (
    IndexStatus,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSource,
    ReviewStatus,
)
from app.schemas.api import DocumentMetadataRequest


class DocumentProcessingError(RuntimeError):
    pass


def _decode_text(raw: bytes, mime_type: str | None, file_name: str | None) -> str:
    suffix = Path(file_name or "").suffix.lower()
    if mime_type in {"text/plain", "text/markdown", "application/json", "text/csv"} or suffix in {".txt", ".md", ".json", ".csv"}:
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentProcessingError("text uploads must be UTF-8") from exc
    if mime_type == "application/pdf" or suffix == ".pdf":
        try:
            import fitz
        except ImportError as exc:
            raise DocumentProcessingError("PDF processing dependency is not installed") from exc
        try:
            document = fitz.open(stream=raw, filetype="pdf")
            text = "\n".join(page.get_text() for page in document)
            document.close()
            if not text.strip():
                raise DocumentProcessingError("PDF contains no extractable text")
            return text
        except DocumentProcessingError:
            raise
        except Exception as exc:
            raise DocumentProcessingError("PDF could not be parsed") from exc
    raise DocumentProcessingError("unsupported document type; upload PDF, TXT, MD, JSON, or CSV")


def split_text(text: str, max_chars: int = 1200) -> list[str]:
    normalized = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + max_chars, len(normalized))
        if end < len(normalized):
            boundary = max(normalized.rfind("\n", start, end), normalized.rfind(". ", start, end))
            if boundary > start + max_chars // 2:
                end = boundary + 1
        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        start = end
    return chunks


def create_or_get_source(db: Session, metadata: DocumentMetadataRequest) -> KnowledgeSource:
    if metadata.source_id:
        source = db.get(KnowledgeSource, metadata.source_id)
        if source is None:
            raise DocumentProcessingError("source_id does not exist")
        return source
    source = KnowledgeSource(
        name=metadata.source_name or metadata.title,
        title=metadata.title,
        source_type=metadata.source_type,
        authority=metadata.authority,
        jurisdiction=metadata.jurisdiction,
        topic=metadata.topic,
        url=metadata.url,
        version=metadata.version,
        review_status=ReviewStatus.PENDING.value,
        evidence_level=metadata.evidence_level,
    )
    db.add(source)
    db.flush()
    return source


def create_document(
    db: Session,
    *,
    raw_content: bytes,
    metadata: DocumentMetadataRequest,
    created_by: str,
    original_filename: str | None = None,
) -> KnowledgeDocument:
    if not raw_content:
        raise DocumentProcessingError("document is empty")
    source = create_or_get_source(db, metadata)
    file_name = sanitize_filename(original_filename or metadata.title)
    document = KnowledgeDocument(
        source_id=source.id,
        title=metadata.title,
        domain=metadata.domain,
        subdomain=metadata.subdomain,
        language=metadata.language,
        region=metadata.region,
        pregnancy_stage=metadata.pregnancy_stage,
        review_status=ReviewStatus.PENDING.value,
        index_status=IndexStatus.PENDING.value,
        content_hash=sha256_bytes(raw_content),
        file_name=file_name,
        mime_type="application/octet-stream",
        raw_content=raw_content,
        active=False,
        created_by=created_by,
    )
    db.add(document)
    db.flush()
    return document


def reindex_document(db: Session, document: KnowledgeDocument) -> int:
    if document.raw_content is None:
        document.index_status = IndexStatus.FAILED.value
        db.flush()
        raise DocumentProcessingError("document has no stored content")
    document.index_status = IndexStatus.INDEXING.value
    db.flush()
    try:
        text = _decode_text(document.raw_content, document.mime_type, document.file_name)
        pieces = split_text(text)
        for old_chunk in list(document.chunks):
            db.delete(old_chunk)
        db.flush()
        for index, content in enumerate(pieces):
            db.add(
                KnowledgeChunk(
                    document_id=document.id,
                    source_id=document.source_id,
                    chunk_index=index,
                    content=content,
                    extra_metadata={"char_count": len(content)},
                )
            )
        document.index_status = IndexStatus.INDEXED.value
        db.flush()
        return len(pieces)
    except Exception:
        document.index_status = IndexStatus.FAILED.value
        db.flush()
        raise
