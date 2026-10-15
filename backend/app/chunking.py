"""Chunk page text into overlapping windows, preserving page + offset metadata."""
from dataclasses import dataclass

from app.pdf_processing import PageText


@dataclass
class Chunk:
    chunk_index: int
    page_number: int
    char_start: int
    char_end: int
    text: str


def chunk_pages(pages: list[PageText], chunk_size: int, overlap: int) -> list[Chunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[Chunk] = []
    idx = 0
    for page in pages:
        text = page.text
        if not text:
            continue
        start = 0
        n = len(text)
        while start < n:
            end = min(start + chunk_size, n)
            # avoid splitting mid-word when not at the end of the page
            if end < n:
                boundary = text.rfind(" ", start, end)
                if boundary != -1 and boundary > start:
                    end = boundary
            piece = text[start:end].strip()
            if piece:
                chunks.append(
                    Chunk(
                        chunk_index=idx,
                        page_number=page.page_number,
                        char_start=start,
                        char_end=end,
                        text=piece,
                    )
                )
                idx += 1
            if end >= n:
                break
            start = max(end - overlap, start + 1)
    return chunks
