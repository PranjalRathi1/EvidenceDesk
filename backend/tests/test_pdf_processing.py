import fitz
import pytest

from app.pdf_processing import UnsupportedPDFError, compute_content_hash, extract_pages
from tests.conftest import FIXTURES_DIR


def test_extract_pages_returns_one_entry_per_page():
    data = (FIXTURES_DIR / "operating_systems_notes.pdf").read_bytes()
    result = extract_pages(data)
    assert result.page_count == 6
    assert len(result.pages) == 6
    assert result.empty_pages == []


def test_extract_pages_preserves_page_order_and_content():
    data = (FIXTURES_DIR / "operating_systems_notes.pdf").read_bytes()
    result = extract_pages(data)
    assert [p.page_number for p in result.pages] == [1, 2, 3, 4, 5, 6]
    assert "Deadlocks" in result.pages[3].text
    assert "Virtual Memory" in result.pages[4].text
    # citation must never point to an unrelated page because of incorrect indexing
    assert "Deadlocks" not in result.pages[4].text


def test_blank_pdf_raises_unsupported_error():
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    blank_bytes = doc.tobytes()
    doc.close()

    with pytest.raises(UnsupportedPDFError):
        extract_pages(blank_bytes)


def test_malformed_bytes_raise_unsupported_error():
    with pytest.raises(UnsupportedPDFError):
        extract_pages(b"this is not a pdf file")


def test_content_hash_is_stable_and_sensitive_to_content():
    a = compute_content_hash(b"hello")
    b = compute_content_hash(b"hello")
    c = compute_content_hash(b"hello!")
    assert a == b
    assert a != c
