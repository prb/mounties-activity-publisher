"""Tests for Cloud Functions (Searcher and Scraper)."""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, call
import pytz

from src.functions import searcher_handler, scraper_handler
from src.models import Activity, Leader


def _make_activity(slug: str) -> Activity:
    """Build a minimal single-pass (place-less) Activity for searcher tests."""
    return Activity(
        activity_permalink=f"https://www.mountaineers.org/activities/activities/{slug}",
        title="Backcountry Ski/Snowboard - Somewhere",
        description="desc",
        difficulty_rating=["M1 Intermediate Ski"],
        activity_date=datetime(2026, 2, 10, 8, 0, 0, tzinfo=pytz.UTC),
        leader=Leader(leader_permalink="https://www.mountaineers.org/members/x", name="X"),
        place_name="Somewhere",
        activity_type="Backcountry Skiing",
    )


def _mock_searcher_deps(mocker, activities, next_page_url=None):
    """Patch the searcher's fetch/parse/db/enqueue dependencies. Returns a dict
    of the mocks for assertions."""
    mocker.patch('src.functions.searcher.is_processing_enabled', return_value=True)
    mock_fetch = mocker.patch('src.functions.searcher.fetch_search_results', return_value='<html></html>')
    mock_parse = mocker.patch('src.functions.searcher.parse_activity_listing',
                              return_value=(activities, next_page_url))
    mocker.patch('src.functions.searcher.create_or_update_leader')
    mock_create = mocker.patch('src.functions.searcher.create_activity')
    mock_create.return_value = MagicMock(id='some-id')
    mocker.patch('src.functions.searcher.update_search_status')
    mock_publish = mocker.patch('src.functions.searcher.enqueue_publish_task')
    mock_search = mocker.patch('src.functions.searcher.enqueue_search_task')
    return {
        'fetch': mock_fetch,
        'parse': mock_parse,
        'create_activity': mock_create,
        'enqueue_publish': mock_publish,
        'enqueue_search': mock_search,
    }


@pytest.fixture
def activity_detail_html():
    """Load sample activity detail HTML."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_activity_detail.html"
    return fixture_path.read_text()


# Searcher Function Tests (single-pass)

def test_searcher_handler_success(mocker):
    """Single-pass: all new activities are stored and publish tasks enqueued."""
    activities = [_make_activity(f"activity-{i}") for i in range(3)]
    mocks = _mock_searcher_deps(mocker, activities, next_page_url=None)
    mocker.patch('src.functions.searcher.activity_exists', return_value=False)

    result = searcher_handler(start_index=0)

    assert result['status'] == 'success'
    assert result['activities_found'] == 3
    assert result['new_activities'] == 3
    assert result['has_next_page'] is False

    mocks['fetch'].assert_called_once_with(start_index=0, activity_type='Backcountry Skiing')
    # Single-pass: publish tasks enqueued directly, no detail fetch/scrape.
    assert mocks['enqueue_publish'].call_count == 3
    assert mocks['create_activity'].call_count == 3
    mocks['enqueue_search'].assert_not_called()


def test_searcher_handler_with_next_page(mocker):
    """A next-page URL triggers another search task at start_index + 20."""
    activities = [_make_activity(f"activity-{i}") for i in range(2)]
    mocks = _mock_searcher_deps(mocker, activities, next_page_url='https://example/@@faceted_query?b_start:int=20')
    mocker.patch('src.functions.searcher.activity_exists', return_value=False)

    result = searcher_handler(start_index=0)

    assert result['status'] == 'success'
    assert result['has_next_page'] is True
    mocks['enqueue_search'].assert_called_once_with(20, 'Backcountry Skiing')


def test_searcher_handler_custom_activity_type(mocker):
    """Custom activity type is threaded through fetch and next-page enqueue."""
    mocks = _mock_searcher_deps(mocker, [_make_activity("a-0")],
                                next_page_url='https://example/@@faceted_query?b_start:int=20')
    mocker.patch('src.functions.searcher.activity_exists', return_value=False)

    result = searcher_handler(start_index=0, activity_type='Rock Climbing')

    mocks['fetch'].assert_called_once_with(start_index=0, activity_type='Rock Climbing')
    mocks['enqueue_search'].assert_called_once_with(20, 'Rock Climbing')
    assert result['status'] == 'success'


def test_searcher_handler_http_error(mocker):
    """Test searcher handling HTTP error."""
    mocker.patch('src.functions.searcher.is_processing_enabled', return_value=True)
    mocker.patch('src.functions.searcher.update_search_status')
    mock_fetch = mocker.patch('src.functions.searcher.fetch_search_results')
    mock_fetch.side_effect = Exception('Network error')

    result = searcher_handler(start_index=0)

    assert result['status'] == 'error'
    assert 'error' in result
    assert 'Network error' in result['error']


def test_searcher_handler_continues_on_store_failure(mocker):
    """A failure storing one activity does not abort the whole page."""
    activities = [_make_activity(f"activity-{i}") for i in range(3)]
    mocks = _mock_searcher_deps(mocker, activities, next_page_url=None)
    mocker.patch('src.functions.searcher.activity_exists', return_value=False)
    # Second activity's publish enqueue fails.
    mocks['enqueue_publish'].side_effect = [None, Exception('enqueue failed'), None]

    result = searcher_handler(start_index=0)

    assert result['status'] == 'success'
    assert result['activities_found'] == 3
    # Two succeeded, one failed mid-store.
    assert result['new_activities'] == 2


def test_searcher_handler_skips_existing_activities(mocker):
    """Activities already in Firestore are skipped (dedup)."""
    activities = [_make_activity(f"activity-{i}") for i in range(5)]
    mocks = _mock_searcher_deps(mocker, activities, next_page_url=None)
    # First 2 already exist, last 3 are new.
    mock_exists = mocker.patch('src.functions.searcher.activity_exists',
                               side_effect=[True, True, False, False, False])

    result = searcher_handler(start_index=0)

    assert result['status'] == 'success'
    assert result['activities_found'] == 5
    assert result['new_activities'] == 3
    assert mocks['enqueue_publish'].call_count == 3
    assert mock_exists.call_count == 5


def test_searcher_handler_skipped_when_processing_disabled(mocker):
    """When processing is disabled the searcher does no work."""
    mocker.patch('src.functions.searcher.is_processing_enabled', return_value=False)
    mock_fetch = mocker.patch('src.functions.searcher.fetch_search_results')

    result = searcher_handler(start_index=0)

    assert result['status'] == 'skipped'
    mock_fetch.assert_not_called()


# Scraper Function Tests

def test_scraper_handler_success(mocker, activity_detail_html):
    """Test successful scraping and storing of activity."""
    # Mock fetch_page
    mock_fetch = mocker.patch('src.functions.scraper.fetch_page')
    mock_fetch.return_value = activity_detail_html

    # Mock Firestore operations
    mock_create_leader = mocker.patch('src.functions.scraper.create_or_update_leader')
    mock_leader_ref = MagicMock()
    mock_leader_ref.id = 'randolph-oakley'
    mock_create_leader.return_value = mock_leader_ref

    mock_create_place = mocker.patch('src.functions.scraper.create_or_update_place')
    mock_place_ref = MagicMock()
    mock_place_ref.id = 'ski-resorts-nordic-centers_snoqualmie-summit-ski-areas'
    mock_create_place.return_value = mock_place_ref

    # Mock create_activity - now idempotent, no transaction needed
    mock_create_activity = mocker.patch('src.functions.scraper.create_activity')
    mock_activity_ref = MagicMock()
    mock_activity_ref.id = 'backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10'
    mock_create_activity.return_value = mock_activity_ref

    # Mock enqueue_publish_task
    mock_enqueue_publish = mocker.patch('src.functions.scraper.enqueue_publish_task')

    # Call handler
    activity_url = 'https://www.mountaineers.org/activities/activities/backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10'
    result = scraper_handler(activity_url=activity_url)

    # Verify result
    assert result['status'] == 'success'
    assert result['activity_id'] == 'backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10'

    # Verify all operations were called
    mock_fetch.assert_called_once_with(activity_url)
    mock_create_leader.assert_called_once()
    mock_create_place.assert_called_once()
    mock_create_activity.assert_called_once()
    mock_enqueue_publish.assert_called_once_with('backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10')


# Removed test_scraper_handler_skips_existing_activity - scraper is now idempotent
# and will overwrite existing activities instead of skipping them

def test_scraper_handler_missing_url(mocker):
    """Test that scraper returns error if activity_url is missing."""
    result = scraper_handler()

    assert result['status'] == 'error'
    assert 'Missing required parameter' in result['error']


def test_scraper_handler_http_error(mocker):
    """Test scraper handling HTTP error."""
    # Mock fetch_page to raise exception
    mock_fetch = mocker.patch('src.functions.scraper.fetch_page')
    mock_fetch.side_effect = Exception("HTTP error")

    # Call handler
    result = scraper_handler(
        activity_url='https://www.mountaineers.org/activities/activities/some-activity'
    )

    # Verify error response
    assert result['status'] == 'error'
    assert 'HTTP error' in result['error']


def test_scraper_handler_continues_on_publish_enqueue_failure(mocker, activity_detail_html):
    """Test that scraper succeeds even if publish enqueue fails."""
    # Mock fetch_page
    mock_fetch = mocker.patch('src.functions.scraper.fetch_page')
    mock_fetch.return_value = activity_detail_html

    # Mock Firestore operations

    mock_create_leader = mocker.patch('src.functions.scraper.create_or_update_leader')
    mock_leader_ref = MagicMock()
    mock_leader_ref.id = 'randolph-oakley'
    mock_create_leader.return_value = mock_leader_ref

    mock_create_place = mocker.patch('src.functions.scraper.create_or_update_place')
    mock_place_ref = MagicMock()
    mock_place_ref.id = 'ski-resorts-nordic-centers_snoqualmie-summit-ski-areas'
    mock_create_place.return_value = mock_place_ref

    # Mock Transaction
    mock_get_transaction = mocker.patch('src.functions.scraper.get_transaction')
    mock_transaction = MagicMock()
    mock_get_transaction.return_value = mock_transaction

    mock_create_activity = mocker.patch('src.functions.scraper.create_activity')
    mock_activity_ref = MagicMock()
    mock_activity_ref.id = 'backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10'
    mock_create_activity.return_value = mock_activity_ref

    # Mock enqueue_publish_task to raise exception
    mock_enqueue_publish = mocker.patch('src.functions.scraper.enqueue_publish_task')
    mock_enqueue_publish.side_effect = Exception('Enqueue failed')

    # Call handler
    activity_url = 'https://www.mountaineers.org/activities/activities/backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10'
    result = scraper_handler(activity_url=activity_url)

    # Should still return success (activity was created)
    assert result['status'] == 'success'
    assert result['activity_id'] == 'backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10'
