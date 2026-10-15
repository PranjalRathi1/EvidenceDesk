"""Page-aware PDF text extraction using PyMuPDF."""
import hashlib
from dataclasses import dataclass

import fitz  # PyMuPDF


class UnsupportedPDFError(Exception):
    """Raised when a PDF has no extractable text (e.g. a scanned image-only document)."""


@dataclass
class PageText:
    page_number: int  # 1-indexed
    text: str


@dataclass
class ExtractionResult:
    pages: list[PageText]
    page_count: int
    empty_pages: list[int]


def compute_content_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


MIN_CHARS_FOR_TEXT_PAGE = 10


def extract_pages(file_bytes: bytes) -> ExtractionResult:
    """Extract text page by page. Raises UnsupportedPDFError if the document
    appears to be scanned/image-only (no page has meaningful extractable text)."""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:  # malformed file
        raise UnsupportedPDFError(f"Could not open file as a PDF: {exc}") from exc

    pages: list[PageText] = []
    empty_pages: list[int] = []
    try:
        for i in range(doc.page_count):
            page = doc.load_page(i)
            text = page.get_text("text") or ""
            text = text.strip()
            page_number = i + 1
            if len(text) < MIN_CHARS_FOR_TEXT_PAGE:
                empty_pages.append(page_number)
            pages.append(PageText(page_number=page_number, text=text))
    finally:
        doc.close()

    page_count = len(pages)
    non_empty = page_count - len(empty_pages)
    if page_count == 0:
        raise UnsupportedPDFError("The PDF has no pages.")
    if non_empty == 0:
        raise UnsupportedPDFError(
            "No extractable text was found on any page. This looks like a scanned or "
            "image-only PDF. OCR is not supported in this prototype — try a text-based PDF."
        )

    return ExtractionResult(pages=pages, page_count=page_count, empty_pages=empty_pages)
