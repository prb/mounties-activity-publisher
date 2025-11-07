"""Tests for Cloud Functions (Searcher and Scraper)."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, call

from src.functions import searcher_handler, scraper_handler


@pytest.fixture
def search_response_html():
    """Load sample search response HTML."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_activity_search_response.html"
    return fixture_path.read_text()


@pytest.fixture
def search_response_with_next_html():
    """Load sample search response with next page."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_activity_search_response_1.html"
    return fixture_path.read_text()


@pytest.fixture
def activity_detail_html():
    """Load sample activity detail HTML."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_activity_detail.html"
    return fixture_path.read_text()


# Searcher Function Tests

def test_searcher_handler_success(mocker, search_response_html):
    """Test successful search with no next page."""
    # Mock fetch_search_results
    mock_fetch = mocker.patch('src.functions.searcher.fetch_search_results')
    mock_fetch.return_value = search_response_html

    # Mock enqueue functions
    mock_enqueue_scrape = mocker.patch('src.functions.searcher.enqueue_scrape_task')
    mock_enqueue_search = mocker.patch('src.functions.searcher.enqueue_search_task')

    # Call handler
    result = searcher_handler({'start_index': 0})

    # Verify result
    assert result['status'] == 'success'
    assert result['activities_found'] == 14
    assert result['has_next_page'] is False

    # Verify fetch was called correctly
    mock_fetch.assert_called_once_with(start_index=0, activity_type='Backcountry Skiing')

    # Verify scraper tasks were enqueued for each activity
    assert mock_enqueue_scrape.call_count == 14

    # Verify no next search task was enqueued (no next page)
    mock_enqueue_search.assert_not_called()


def test_searcher_handler_with_next_page(mocker, search_response_with_next_html):
    """Test search with next page."""
    # Mock fetch_search_results
    mock_fetch = mocker.patch('src.functions.searcher.fetch_search_results')
    mock_fetch.return_value = search_response_with_next_html

    # Mock enqueue functions
    mock_enqueue_scrape = mocker.patch('src.functions.searcher.enqueue_scrape_task')
    mock_enqueue_search = mocker.patch('src.functions.searcher.enqueue_search_task')

    # Call handler
    result = searcher_handler({'start_index': 0})

    # Verify result
    assert result['status'] == 'success'
    assert result['activities_found'] == 20
    assert result['has_next_page'] is True

    # Verify scraper tasks were enqueued for each activity
    assert mock_enqueue_scrape.call_count == 20

    # Verify next search task was enqueued
    mock_enqueue_search.assert_called_once_with(20, 'Backcountry Skiing')


def test_searcher_handler_custom_activity_type(mocker, search_response_html):
    """Test search with custom activity type."""
    # Mock fetch_search_results
    mock_fetch = mocker.patch('src.functions.searcher.fetch_search_results')
    mock_fetch.return_value = search_response_html

    # Mock enqueue functions
    mocker.patch('src.functions.searcher.enqueue_scrape_task')
    mocker.patch('src.functions.searcher.enqueue_search_task')

    # Call handler with custom activity type
    result = searcher_handler({
        'start_index': 0,
        'activity_type': 'Rock Climbing'
    })

    # Verify fetch was called with custom activity type
    mock_fetch.assert_called_once_with(start_index=0, activity_type='Rock Climbing')

    assert result['status'] == 'success'


def test_searcher_handler_http_error(mocker):
    """Test searcher handling HTTP error."""
    # Mock fetch to raise an exception
    mock_fetch = mocker.patch('src.functions.searcher.fetch_search_results')
    mock_fetch.side_effect = Exception('Network error')

    # Call handler
    result = searcher_handler({'start_index': 0})

    # Verify error response
    assert result['status'] == 'error'
    assert 'error' in result
    assert 'Network error' in result['error']


def test_searcher_handler_continues_on_enqueue_failure(mocker, search_response_html):
    """Test that searcher continues even if some enqueue operations fail."""
    # Mock fetch_search_results
    mock_fetch = mocker.patch('src.functions.searcher.fetch_search_results')
    mock_fetch.return_value = search_response_html

    # Mock enqueue to fail on some calls
    mock_enqueue_scrape = mocker.patch('src.functions.searcher.enqueue_scrape_task')
    mock_enqueue_scrape.side_effect = [
        None,  # First succeeds
        Exception('Task enqueue failed'),  # Second fails
        None,  # Rest succeed
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    ]

    # Call handler
    result = searcher_handler({'start_index': 0})

    # Should still return success
    assert result['status'] == 'success'
    assert result['activities_found'] == 14


# Scraper Function Tests

def test_scraper_handler_success(mocker, activity_detail_html):
    """Test successful scraping and storing of activity."""
    # Mock fetch_page
    mock_fetch = mocker.patch('src.functions.scraper.fetch_page')
    mock_fetch.return_value = activity_detail_html

    # Mock Firestore operations
    mock_activity_exists = mocker.patch('src.functions.scraper.activity_exists')
    mock_activity_exists.return_value = False

    mock_create_leader = mocker.patch('src.functions.scraper.create_or_update_leader')
    mock_leader_ref = MagicMock()
    mock_leader_ref.id = 'randolph-oakley'
    mock_create_leader.return_value = mock_leader_ref

    mock_create_place = mocker.patch('src.functions.scraper.create_or_update_place')
    mock_place_ref = MagicMock()
    mock_place_ref.id = 'ski-resorts-nordic-centers_snoqualmie-summit-ski-areas'
    mock_create_place.return_value = mock_place_ref

    mock_create_activity = mocker.patch('src.functions.scraper.create_activity')
    mock_activity_ref = MagicMock()
    mock_activity_ref.id = 'backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10'
    mock_create_activity.return_value = mock_activity_ref

    # Mock enqueue_publish_task
    mock_enqueue_publish = mocker.patch('src.functions.scraper.enqueue_publish_task')

    # Call handler
    activity_url = 'https://www.mountaineers.org/activities/activities/backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10'
    result = scraper_handler({'activity_url': activity_url})

    # Verify result
    assert result['status'] == 'success'
    assert result['activity_id'] == 'backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10'

    # Verify all operations were called
    mock_fetch.assert_called_once_with(activity_url)
    mock_activity_exists.assert_called_once()
    mock_create_leader.assert_called_once()
    mock_create_place.assert_called_once()
    mock_create_activity.assert_called_once()
    mock_enqueue_publish.assert_called_once_with('backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10')


def test_scraper_handler_skips_existing_activity(mocker):
    """Test that scraper skips activities that already exist."""
    # Mock activity_exists to return True
    mock_activity_exists = mocker.patch('src.functions.scraper.activity_exists')
    mock_activity_exists.return_value = True

    # Mock other functions (should not be called)
    mock_fetch = mocker.patch('src.functions.scraper.fetch_page')
    mock_create_activity = mocker.patch('src.functions.scraper.create_activity')

    # Call handler
    activity_url = 'https://www.mountaineers.org/activities/activities/some-existing-activity'
    result = scraper_handler({'activity_url': activity_url})

    # Verify result
    assert result['status'] == 'skipped'
    assert result['activity_id'] == 'some-existing-activity'
    assert 'already exists' in result['reason']

    # Verify fetch and create were not called
    mock_fetch.assert_not_called()
    mock_create_activity.assert_not_called()


def test_scraper_handler_missing_url(mocker):
    """Test that scraper returns error if activity_url is missing."""
    result = scraper_handler({})

    assert result['status'] == 'error'
    assert 'Missing required parameter' in result['error']


def test_scraper_handler_http_error(mocker):
    """Test scraper handling HTTP error."""
    # Mock activity_exists
    mock_activity_exists = mocker.patch('src.functions.scraper.activity_exists')
    mock_activity_exists.return_value = False

    # Mock fetch to raise an exception
    mock_fetch = mocker.patch('src.functions.scraper.fetch_page')
    mock_fetch.side_effect = Exception('Network error')

    # Call handler
    result = scraper_handler({
        'activity_url': 'https://www.mountaineers.org/activities/activities/some-activity'
    })

    # Verify error response
    assert result['status'] == 'error'
    assert 'Network error' in result['error']


def test_scraper_handler_continues_on_publish_enqueue_failure(mocker, activity_detail_html):
    """Test that scraper succeeds even if publish enqueue fails."""
    # Mock fetch_page
    mock_fetch = mocker.patch('src.functions.scraper.fetch_page')
    mock_fetch.return_value = activity_detail_html

    # Mock Firestore operations
    mock_activity_exists = mocker.patch('src.functions.scraper.activity_exists')
    mock_activity_exists.return_value = False

    mock_create_leader = mocker.patch('src.functions.scraper.create_or_update_leader')
    mock_leader_ref = MagicMock()
    mock_leader_ref.id = 'randolph-oakley'
    mock_create_leader.return_value = mock_leader_ref

    mock_create_place = mocker.patch('src.functions.scraper.create_or_update_place')
    mock_place_ref = MagicMock()
    mock_place_ref.id = 'ski-resorts-nordic-centers_snoqualmie-summit-ski-areas'
    mock_create_place.return_value = mock_place_ref

    mock_create_activity = mocker.patch('src.functions.scraper.create_activity')
    mock_activity_ref = MagicMock()
    mock_activity_ref.id = 'backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10'
    mock_create_activity.return_value = mock_activity_ref

    # Mock enqueue_publish_task to raise exception
    mock_enqueue_publish = mocker.patch('src.functions.scraper.enqueue_publish_task')
    mock_enqueue_publish.side_effect = Exception('Enqueue failed')

    # Call handler
    activity_url = 'https://www.mountaineers.org/activities/activities/backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10'
    result = scraper_handler({'activity_url': activity_url})

    # Should still return success (activity was created)
    assert result['status'] == 'success'
    assert result['activity_id'] == 'backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10'
