"""Tests for activity detail parser."""

import pytest
from pathlib import Path
from datetime import datetime
import pytz

from src.parsers.detail_parser import (
    parse_activity_detail,
    extract_title,
    extract_description,
    extract_activity_date,
    extract_difficulty_rating,
    extract_leader,
    extract_place,
)
from src.models import Activity, Leader, Place
from lxml import html


@pytest.fixture
def activity_detail_html():
    """Load sample activity detail page."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_activity_detail.html"
    return fixture_path.read_text()


@pytest.fixture
def activity_detail_tree(activity_detail_html):
    """Parse activity detail HTML into tree."""
    return html.fromstring(activity_detail_html)


def test_extract_title(activity_detail_tree):
    """Test extracting activity title."""
    title = extract_title(activity_detail_tree)

    assert title == "Backcountry Ski/Snowboard - Snoqualmie Summit West"
    assert isinstance(title, str)


def test_extract_description(activity_detail_tree):
    """Test extracting activity description."""
    description = extract_description(activity_detail_tree)

    assert "Tuesday night headlamp workout series" in description
    assert "backcountry skiers" in description
    assert isinstance(description, str)


def test_extract_activity_date(activity_detail_tree):
    """Test extracting and parsing activity date."""
    activity_date = extract_activity_date(activity_detail_tree)

    # Should be Feb 10, 2026 in Pacific time, converted to UTC
    assert isinstance(activity_date, datetime)
    assert activity_date.year == 2026
    assert activity_date.month == 2
    assert activity_date.day == 10 or activity_date.day == 11  # Could be 11 in UTC
    assert activity_date.tzinfo == pytz.UTC


def test_extract_difficulty_rating(activity_detail_tree):
    """Test extracting difficulty rating."""
    ratings = extract_difficulty_rating(activity_detail_tree)

    assert isinstance(ratings, list)
    assert len(ratings) > 0
    assert "M1 Intermediate Ski" in ratings or any("M1" in r and "Intermediate" in r for r in ratings)


def test_extract_leader(activity_detail_tree):
    """Test extracting leader information."""
    leader = extract_leader(activity_detail_tree)

    assert isinstance(leader, Leader)
    assert leader.name == "Randy Oakley"
    assert "randolph-oakley" in leader.leader_permalink
    assert leader.leader_permalink.startswith("https://www.mountaineers.org/members/")

    # Test document ID extraction
    assert leader.document_id == "randolph-oakley"


def test_extract_place(activity_detail_tree):
    """Test extracting place information."""
    place = extract_place(activity_detail_tree)

    assert isinstance(place, Place)
    assert place.name == "Snoqualmie Summit Ski Areas"
    assert place.place_permalink == "https://www.mountaineers.org/activities/routes-places/ski-resorts-nordic-centers/snoqualmie-summit-ski-areas"

    # Test document ID extraction
    assert place.document_id == "ski-resorts-nordic-centers_snoqualmie-summit-ski-areas"


def test_parse_activity_detail(activity_detail_html):
    """Test full parse of activity detail page."""
    activity_url = "https://www.mountaineers.org/activities/activities/backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10"
    activity = parse_activity_detail(activity_detail_html, activity_url)

    # Check Activity object
    assert isinstance(activity, Activity)
    assert activity.activity_permalink == activity_url
    assert activity.title == "Backcountry Ski/Snowboard - Snoqualmie Summit West"
    assert "headlamp workout" in activity.description
    assert len(activity.difficulty_rating) > 0
    assert isinstance(activity.activity_date, datetime)

    # Check Leader
    assert isinstance(activity.leader, Leader)
    assert activity.leader.name == "Randy Oakley"

    # Check Place
    assert isinstance(activity.place, Place)
    assert activity.place.name == "Snoqualmie Summit Ski Areas"

    # Check document IDs
    assert activity.document_id == "backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10"
    assert activity.leader.document_id == "randolph-oakley"
    assert activity.place.document_id == "ski-resorts-nordic-centers_snoqualmie-summit-ski-areas"

    # Check discord_message_id defaults to None
    assert activity.discord_message_id is None


def test_missing_title():
    """Test that missing title raises error."""
    empty_tree = html.fromstring("<html><body></body></html>")

    with pytest.raises(ValueError, match="Could not find activity title"):
        extract_title(empty_tree)


def test_missing_date():
    """Test that missing date raises error."""
    empty_tree = html.fromstring("<html><body></body></html>")

    with pytest.raises(ValueError, match="Could not find activity date"):
        extract_activity_date(empty_tree)


def test_missing_leader():
    """Test that missing leader raises error."""
    empty_tree = html.fromstring("<html><body></body></html>")

    with pytest.raises(ValueError, match="Could not find leader"):
        extract_leader(empty_tree)


def test_missing_place():
    """Test that missing place raises error."""
    empty_tree = html.fromstring("<html><body></body></html>")

    with pytest.raises(ValueError, match="Could not find place"):
        extract_place(empty_tree)


def test_empty_description():
    """Test that missing description returns empty string."""
    empty_tree = html.fromstring("<html><body></body></html>")

    description = extract_description(empty_tree)
    assert description == ""


def test_empty_difficulty():
    """Test that missing difficulty returns empty list."""
    empty_tree = html.fromstring("<html><body></body></html>")

    ratings = extract_difficulty_rating(empty_tree)
    assert ratings == []
