"""Tests for the HTTP client (approved URL, bypass header, cache-busting)."""

import re
import pytest

from src import http_client
from src.http_client import (
    fetch_page,
    fetch_search_results,
    APPROVED_URL,
    FACETED_QUERY_URL,
    SCRAPER_HEADER_NAME,
    SCRAPER_HEADER_VALUE,
    USER_AGENT,
)


class _FakeResponse:
    def __init__(self, text='<html></html>'):
        self.text = text

    def raise_for_status(self):
        pass


@pytest.fixture
def captured_get(mocker):
    """Patch requests.get and capture the (url, headers) it was called with."""
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append({'url': url, 'headers': headers or {}, 'timeout': timeout})
        return _FakeResponse()

    mocker.patch('src.http_client.requests.get', side_effect=fake_get)
    return calls


def test_approved_url_gets_bypass_header_and_cache_bust(captured_get):
    fetch_page(FACETED_QUERY_URL + '?c4[]=Backcountry Skiing&b_start:int=0')

    call = captured_get[0]
    assert call['headers'][SCRAPER_HEADER_NAME] == SCRAPER_HEADER_VALUE
    assert call['headers']['Cache-Control'] == 'no-cache'
    assert call['headers']['User-Agent'] == USER_AGENT
    # Cache-buster appended (the request already had a query string).
    assert re.search(r'&_cb=[0-9a-f]+$', call['url'])


def test_paginated_approved_url_also_gets_header(captured_get):
    """A next-page @@faceted_query URL is still under the approved path."""
    fetch_page(FACETED_QUERY_URL + '?c4[]=Backcountry Skiing&b_start:int=20')
    assert SCRAPER_HEADER_NAME in captured_get[0]['headers']


def test_cache_buster_uses_question_mark_when_no_query(captured_get):
    fetch_page(APPROVED_URL)
    assert re.search(r'\?_cb=[0-9a-f]+$', captured_get[0]['url'])


def test_other_urls_do_not_get_bypass_header(captured_get):
    fetch_page('https://www.mountaineers.org/activities/activities/some-activity')

    call = captured_get[0]
    assert SCRAPER_HEADER_NAME not in call['headers']
    assert 'Cache-Control' not in call['headers']
    assert call['headers']['User-Agent'] == USER_AGENT
    # No cache-buster on non-approved URLs.
    assert '_cb=' not in call['url']


def test_cache_buster_is_unique_per_request(captured_get):
    fetch_page(APPROVED_URL)
    fetch_page(APPROVED_URL)
    assert captured_get[0]['url'] != captured_get[1]['url']


def test_fetch_search_results_builds_c4_faceted_query(captured_get):
    fetch_search_results(start_index=40, activity_type='Backcountry Skiing')

    url = captured_get[0]['url']
    assert url.startswith(FACETED_QUERY_URL + '?')
    assert 'c4[]=Backcountry' in url
    assert 'b_start:int=40' in url
    # Header applied because it's the approved endpoint.
    assert SCRAPER_HEADER_NAME in captured_get[0]['headers']
