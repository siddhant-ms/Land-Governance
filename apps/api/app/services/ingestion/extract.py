"""Text extraction + metadata extraction. Returns pages so every chunk keeps its page number."""
import io
import re
from dataclasses import dataclass, field
from datetime import date

import yaml
from pypdf import PdfReader

from app.core.errors import AppError

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown"}
PAGE_MARKER = re.compile(r"<!--\s*page:\s*(\d+)\s*-->", re.I)
FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


@dataclass
class ExtractedDocument:
    pages: list[tuple[int, str]]  # (page_no, text)
    metadata: dict = field(default_factory=dict)  # best-effort metadata found inside the file
    quality: float = 1.0
    warnings: list[str] = field(default_factory=list)


def validate_upload(filename: str, data: bytes, max_bytes: int) -> str:
    """Extension allow-list, size cap and magic-byte check. Returns normalised extension."""
    name = filename.lower().strip()
    ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise AppError(415, "UNSUPPORTED_FILE_TYPE", f"Unsupported file type '{ext or 'none'}'. Allowed: PDF, TXT, Markdown.")
    if len(data) == 0:
        raise AppError(422, "EMPTY_FILE", "The uploaded file is empty.")
    if len(data) > max_bytes:
        raise AppError(413, "FILE_TOO_LARGE", f"File exceeds the {max_bytes // (1024 * 1024)} MB limit.")
    if ext == ".pdf" and not data.startswith(b"%PDF-"):
        raise AppError(415, "INVALID_PDF", "File content is not a valid PDF (bad magic bytes).")
    if ext != ".pdf":
        if b"\x00" in data[:4096]:
            raise AppError(415, "BINARY_CONTENT", "Text files must not contain binary data.")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            raise AppError(415, "BAD_ENCODING", "Text files must be UTF-8 encoded.")
    return ext


def _parse_date(v) -> date | None:
    if isinstance(v, date):
        return v
    if isinstance(v, int):
        return date(v, 1, 1)
    if isinstance(v, str):
        m = re.match(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", v.strip())
        if m:
            return date(int(m[1]), int(m[2] or 1), int(m[3] or 1))
    return None


def _quality(pages: list[tuple[int, str]]) -> tuple[float, list[str]]:
    total = sum(len(t) for _, t in pages)
    warns: list[str] = []
    if total == 0:
        return 0.0, ["No extractable text (likely a scanned PDF; OCR required)."]
    alpha = sum(c.isalpha() for _, t in pages for c in t) / total
    avg = total / max(len(pages), 1)
    q = min(1.0, alpha / 0.7) * min(1.0, avg / 400)
    if avg < 200:
        warns.append("Very little text per page; document may be scanned or image-based.")
    if alpha < 0.5:
        warns.append("Low alphabetic ratio; extraction may be garbled.")
    return round(q, 3), warns


def extract_text_document(data: bytes, ext: str) -> ExtractedDocument:
    text = data.decode("utf-8")
    meta: dict = {}
    m = FRONT_MATTER.match(text)
    if m:
        try:
            loaded = yaml.safe_load(m.group(1)) or {}
            if isinstance(loaded, dict):
                meta = loaded
        except yaml.YAMLError:
            pass
        text = text[m.end():]
    if "publication_date" in meta:
        meta["publication_date"] = _parse_date(meta["publication_date"])
    parts = PAGE_MARKER.split(text)
    pages: list[tuple[int, str]] = []
    if len(parts) == 1:
        pages = [(1, text.strip())]
    else:
        if parts[0].strip():
            pages.append((1, parts[0].strip()))
        for i in range(1, len(parts), 2):
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if body:
                pages.append((int(parts[i]), body))
    q, w = _quality(pages)
    return ExtractedDocument(pages=pages, metadata=meta, quality=q, warnings=w)


def extract_pdf_document(data: bytes) -> ExtractedDocument:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise AppError(422, "ENCRYPTED_PDF", "Encrypted PDFs are not supported.")
        pages = [(i + 1, (p.extract_text() or "").strip()) for i, p in enumerate(reader.pages)]
    except AppError:
        raise
    except Exception as e:  # pypdf raises many types on malformed input
        raise AppError(422, "PDF_EXTRACTION_FAILED", f"Could not read PDF: {type(e).__name__}") from e
    meta: dict = {}
    info = reader.metadata
    if info:
        if info.title:
            meta["title"] = str(info.title)
        if info.author:
            meta["authors"] = [a.strip() for a in re.split(r"[;,]", str(info.author)) if a.strip()]
        if info.creation_date:
            meta["publication_date"] = info.creation_date.date()
    pages = [(n, t) for n, t in pages if t]
    q, w = _quality(pages) if pages else (0.0, ["No extractable text (likely a scanned PDF; OCR required)."])
    return ExtractedDocument(pages=pages, metadata=meta, quality=q, warnings=w)


def extract(data: bytes, ext: str) -> ExtractedDocument:
    return extract_pdf_document(data) if ext == ".pdf" else extract_text_document(data, ext)
