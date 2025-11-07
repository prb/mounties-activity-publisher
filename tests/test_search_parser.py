"""Tests for search results parser."""

import pytest
from pathlib import Path

from src.parsers.search_parser import (
    parse_search_results,
    extract_activity_urls,
    extract_next_page_url,
)


@pytest.fixture
def search_response_no_next():
    """Load sample search response with no next page (page 1, 14 items)."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_activity_search_response.html"
    return fixture_path.read_text()


@pytest.fixture
def search_response_with_next():
    """Load sample search response with next page (page 2, 20 items)."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_activity_search_response_1.html"
    return fixture_path.read_text()


def test_extract_activity_urls_no_next(search_response_no_next):
    """Test extracting activity URLs from page 1 (no next page)."""
    urls = extract_activity_urls(search_response_no_next)

    # Should find 14 activities on page 1
    assert len(urls) == 14

    # Check that URLs are well-formed
    for url in urls:
        assert url.startswith("https://www.mountaineers.org/activities/activities/")
        assert "backcountry-ski" in url.lower()

    # Spot check first URL
    assert urls[0] == "https://www.mountaineers.org/activities/activities/backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10"


def test_extract_activity_urls_with_next(search_response_with_next):
    """Test extracting activity URLs from page 2 (has next link)."""
    urls = extract_activity_urls(search_response_with_next)

    # Should find 20 activities on page 2
    assert len(urls) == 20

    # Check that URLs are well-formed
    for url in urls:
        assert url.startswith("https://www.mountaineers.org/activities/activities/")


def test_extract_next_page_url_no_next(search_response_no_next):
    """Test that page 1 has no next page URL."""
    next_url = extract_next_page_url(search_response_no_next)

    # Page 1 (last page) should not have a next link
    assert next_url is None


def test_extract_next_page_url_with_next(search_response_with_next):
    """Test that page 2 has next page URL."""
    next_url = extract_next_page_url(search_response_with_next)

    assert next_url is not None
    assert "b_start:int=20" in next_url
    assert "Backcountry" in next_url


def test_parse_search_results_no_next(search_response_no_next):
    """Test full parse of search results without next page."""
    activity_urls, next_page_url = parse_search_results(search_response_no_next)

    assert len(activity_urls) == 14
    assert next_page_url is None


def test_parse_search_results_with_next(search_response_with_next):
    """Test full parse of search results with next page."""
    activity_urls, next_page_url = parse_search_results(search_response_with_next)

    assert len(activity_urls) == 20
    assert next_page_url is not None


def test_empty_html():
    """Test that empty HTML returns empty list."""
    urls = extract_activity_urls("")
    assert urls == []

    next_url = extract_next_page_url("")
    assert next_url is None


def test_malformed_html():
    """Test that malformed HTML doesn't crash."""
    malformed = "<div><span>Not a real result</span></div>"

    urls = extract_activity_urls(malformed)
    assert urls == []

    next_url = extract_next_page_url(malformed)
    assert next_url is None
