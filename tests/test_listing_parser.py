"""Tests for the single-pass listing parser."""

import pytest
from pathlib import Path

from src.parsers.listing_parser import parse_activity_listing


@pytest.fixture
def faceted_query_html():
    """Load the sample @@faceted_query listing response."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_faceted_query_response.html"
    return fixture_path.read_text()


@pytest.fixture
def activities(faceted_query_html):
    acts, _ = parse_activity_listing(faceted_query_html)
    return acts


def test_skips_non_activity_rows(activities):
    """The Route/Place row must be skipped; only the 3 activities remain."""
    assert len(activities) == 3
    for a in activities:
        assert '/activities/activities/' in a.activity_permalink


def test_extracts_next_page_url(faceted_query_html):
    _, next_url = parse_activity_listing(faceted_query_html)
    assert next_url is not None
    assert '@@faceted_query' in next_url
    assert 'b_start:int=20' in next_url


def test_full_field_extraction(activities):
    a = activities[0]
    assert a.document_id == 'backcountry-ski-snowboard-snoqualmie-summit-west-2-2025-12-09'
    assert a.title == 'Backcountry Ski/Snowboard - Snoqualmie Summit West'
    assert a.description.startswith('Tuesday night headlamp')
    assert a.difficulty_rating == ['M1 Intermediate Ski']
    assert a.branch == 'Foothills Branch'
    assert a.leader.name == 'Randy Oakley'
    assert a.leader.leader_permalink == 'https://www.mountaineers.org/members/randolph-oakley'
    assert a.leader.document_id == 'randolph-oakley'


def test_activity_type_strips_trip_suffix(activities):
    """'Backcountry Skiing Trip' -> 'Backcountry Skiing' so the emoji lookup works."""
    assert activities[0].activity_type == 'Backcountry Skiing'


def test_place_name_from_title(activities):
    """Place name is the text after the first ' - ', place object stays None."""
    assert activities[0].place is None
    assert activities[0].place_name == 'Snoqualmie Summit West'
    assert activities[1].place_name == 'Mount Baker Backcountry'


def test_missing_place_in_title(activities):
    """Titles with no ' - ' separator yield place_name None."""
    full_moon = activities[2]
    assert full_moon.title == 'Full Moon Ski'
    assert full_moon.place_name is None
    assert full_moon.place is None


def test_single_digit_day_date(activities):
    """'Tue, Dec  9, 2025' (double space) parses; Dec is PST -> 08:00 UTC."""
    d = activities[0].activity_date
    assert (d.year, d.month, d.day, d.hour) == (2025, 12, 9, 8)


def test_multi_day_uses_start_date(activities):
    """Multi-day 'Feb 11 — Feb 12' uses the start date."""
    d = activities[1].activity_date
    assert (d.year, d.month, d.day, d.hour) == (2026, 2, 11, 8)


def test_multiple_difficulties(activities):
    assert activities[1].difficulty_rating == ['M2 Advanced Ski', 'M3G Advanced Glacier Ski']


def test_branch_optional(activities):
    """Item 3 has no result-branch."""
    assert activities[2].branch is None


def test_no_pagination_yields_none():
    """Activities present but no pagination nav -> next_url is None."""
    html = """
    <div class="result-item">
      <h3 class="result-title">
        <a href="https://www.mountaineers.org/activities/activities/solo-2026-01-01">Solo Ski - Somewhere</a>
      </h3>
      <div class="result-date">Thu, Jan 1, 2026</div>
      <div class="result-leader"><a href="https://www.mountaineers.org/members/x">X</a></div>
    </div>
    """
    activities, next_url = parse_activity_listing(html)
    assert len(activities) == 1
    assert next_url is None


def test_place_name_with_multiple_hyphens():
    """Only the first ' - ' splits title from place; the rest stays in the name."""
    html = """
    <div class="result-item">
      <h3 class="result-title">
        <a href="https://www.mountaineers.org/activities/activities/multi-2026-01-01">Backcountry Ski - Mount Baker - North Ridge</a>
      </h3>
      <div class="result-date">Thu, Jan 1, 2026</div>
      <div class="result-leader"><a href="https://www.mountaineers.org/members/x">X</a></div>
    </div>
    """
    activities, _ = parse_activity_listing(html)
    assert len(activities) == 1
    assert activities[0].place_name == "Mount Baker - North Ridge"


def test_empty_html():
    assert parse_activity_listing('') == ([], None)
    assert parse_activity_listing('   ') == ([], None)


def test_garbage_html():
    activities, next_url = parse_activity_listing('not really <<< html')
    assert activities == []
    assert next_url is None


def test_skips_activity_missing_leader():
    """A row with no leader is skipped rather than failing the whole page."""
    html = """
    <div class="result-item">
      <h3 class="result-title">
        <a href="https://www.mountaineers.org/activities/activities/no-leader-2026-01-01">No Leader - Somewhere</a>
      </h3>
      <div class="result-date">Thu, Jan 1, 2026</div>
    </div>
    """
    activities, _ = parse_activity_listing(html)
    assert activities == []


def test_skips_activity_with_bad_date():
    """A row with an unparseable date is skipped."""
    html = """
    <div class="result-item">
      <h3 class="result-title">
        <a href="https://www.mountaineers.org/activities/activities/bad-date">Bad Date - Somewhere</a>
      </h3>
      <div class="result-date">sometime next week</div>
      <div class="result-leader"><a href="https://www.mountaineers.org/members/x">X</a></div>
    </div>
    """
    activities, _ = parse_activity_listing(html)
    assert activities == []
