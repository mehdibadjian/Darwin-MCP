"""Tests for brain.utils.context_buffer — Flash Summarizer."""
import pytest
from brain.utils.context_buffer import flash_report, compress_search_results


SHORT_TEXT = "Python is great. It is easy to learn."
LONG_TEXT = (
    "The Python programming language was created by Guido van Rossum. "
    "It was first released in 1991. Python emphasizes code readability. "
    "The language uses significant indentation. Python supports multiple "
    "programming paradigms including structured, object-oriented, and functional. "
    "Python is dynamically typed and garbage-collected. It has a comprehensive "
    "standard library. Python is widely used in web development, data science, "
    "artificial intelligence, and scripting. The Python Package Index (PyPI) "
    "hosts hundreds of thousands of third-party packages. CPython is the "
    "reference implementation of Python. Python 3 was released in 2008. "
    "Python 2 reached end-of-life in January 2020. The Zen of Python describes "
    "the guiding principles of Python's design. Python is open source and free. "
) * 5  # Repeat to exceed token budget


def test_short_text_returned_unchanged():
    result = flash_report(SHORT_TEXT, query="python", token_budget=400)
    assert result == SHORT_TEXT


def test_long_text_compressed():
    result = flash_report(LONG_TEXT, query="python programming", token_budget=400)
    char_budget = 400 * 4
    assert len(result) <= char_budget + 50  # allow minor overshoot at sentence boundary


def test_relevant_sentences_preferred():
    result = flash_report(LONG_TEXT, query="web development data science", token_budget=400)
    # The sentence about web development should appear in the flash report.
    assert "web development" in result.lower() or "data science" in result.lower()


def test_empty_text_returns_empty():
    assert flash_report("", query="anything") == ""


def test_no_query_still_compresses():
    result = flash_report(LONG_TEXT, query="", token_budget=100)
    assert len(result) <= 100 * 4 + 50


def test_compress_search_results_adds_flash_report():
    results = [
        {"url": "https://example.com", "title": "Test", "text": LONG_TEXT},
        {"url": "https://other.com", "title": "No text"},
    ]
    out = compress_search_results(results, query="python")
    assert "flash_report" in out[0]
    assert "flash_report" not in out[1]  # no text field, untouched


def test_compress_preserves_original_text():
    results = [{"url": "https://x.com", "text": LONG_TEXT}]
    out = compress_search_results(results, query="python")
    assert out[0]["text"] == LONG_TEXT  # original preserved


def test_compress_empty_results():
    assert compress_search_results([]) == []
