import pytest

from app.chunking import chunk_pages
from app.pdf_processing import PageText


def test_chunking_preserves_page_metadata():
    pages = [PageText(page_number=1, text="A" * 50), PageText(page_number=2, text="B" * 50)]
    chunks = chunk_pages(pages, chunk_size=30, overlap=5)
    assert all(c.page_number in (1, 2) for c in chunks)
    page1_chunks = [c for c in chunks if c.page_number == 1]
    page2_chunks = [c for c in chunks if c.page_number == 2]
    assert all(set(c.text) == {"A"} for c in page1_chunks)
    assert all(set(c.text) == {"B"} for c in page2_chunks)


def test_chunking_respects_overlap():
    text = "word " * 100
    pages = [PageText(page_number=1, text=text.strip())]
    chunks = chunk_pages(pages, chunk_size=50, overlap=10)
    assert len(chunks) > 1
    for c in chunks:
        assert c.char_end - c.char_start <= 50


def test_chunking_skips_empty_pages():
    pages = [PageText(page_number=1, text=""), PageText(page_number=2, text="real content here")]
    chunks = chunk_pages(pages, chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].page_number == 2


def test_chunking_rejects_invalid_overlap():
    with pytest.raises(ValueError):
        chunk_pages([PageText(page_number=1, text="x" * 10)], chunk_size=10, overlap=10)


def test_chunk_indices_are_sequential():
    pages = [PageText(page_number=1, text="word " * 40)]
    chunks = chunk_pages(pages, chunk_size=30, overlap=5)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
