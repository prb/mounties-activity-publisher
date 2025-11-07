"""Tests for Firestore database operations.

These tests require the Firestore emulator to be running:
    firebase emulators:start --only firestore

Or set FIRESTORE_EMULATOR_HOST=localhost:8080
"""

import pytest
from datetime import datetime
import pytz

from src.models import Activity, Leader, Place
from src.db import (
    initialize_firebase,
    get_firestore_client,
    # Leaders
    create_or_update_leader,
    get_leader,
    leader_exists,
    # Places
    create_or_update_place,
    get_place,
    place_exists,
    # Activities
    create_activity,
    get_activity,
    update_activity,
    activity_exists,
    update_discord_message_id,
)


@pytest.fixture(scope="module")
def firestore_client():
    """Initialize Firebase with emulator for testing."""
    initialize_firebase(use_emulator=True)
    return get_firestore_client()


@pytest.fixture(autouse=True)
def cleanup_collections(firestore_client):
    """Clean up test data after each test."""
    yield

    # Clean up collections
    for collection_name in ['activities', 'leaders', 'places']:
        docs = firestore_client.collection(collection_name).list_documents()
        for doc in docs:
            doc.delete()


@pytest.fixture
def sample_leader():
    """Create a sample leader."""
    return Leader(
        leader_permalink="https://www.mountaineers.org/members/randy-oakley",
        name="Randy Oakley"
    )


@pytest.fixture
def sample_place():
    """Create a sample place."""
    return Place(
        place_permalink="https://www.mountaineers.org/activities/routes-places/ski-resorts-nordic-centers/snoqualmie-summit-ski-areas",
        name="Snoqualmie Summit Ski Areas"
    )


@pytest.fixture
def sample_activity(sample_leader, sample_place):
    """Create a sample activity."""
    return Activity(
        activity_permalink="https://www.mountaineers.org/activities/activities/backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10",
        title="Backcountry Ski/Snowboard - Snoqualmie Summit West",
        description="Tuesday night headlamp workout series for backcountry skiers / splitboarders.",
        difficulty_rating=["M1 Intermediate Ski"],
        activity_date=datetime(2026, 2, 10, 8, 0, 0, tzinfo=pytz.UTC),
        leader=sample_leader,
        place=sample_place,
    )


# Leader Tests

def test_create_leader(sample_leader):
    """Test creating a leader."""
    ref = create_or_update_leader(sample_leader)

    assert ref.id == "randolph-oakley"
    assert leader_exists("randolph-oakley")


def test_get_leader(sample_leader):
    """Test retrieving a leader."""
    create_or_update_leader(sample_leader)

    retrieved = get_leader("randolph-oakley")

    assert retrieved is not None
    assert retrieved.name == "Randy Oakley"
    assert retrieved.leader_permalink == sample_leader.leader_permalink
    assert retrieved.document_id == "randolph-oakley"


def test_get_nonexistent_leader():
    """Test retrieving a nonexistent leader."""
    retrieved = get_leader("nonexistent")

    assert retrieved is None


def test_update_leader(sample_leader):
    """Test updating a leader."""
    create_or_update_leader(sample_leader)

    # Update the leader
    sample_leader.name = "Randy J. Oakley"
    create_or_update_leader(sample_leader)

    retrieved = get_leader("randolph-oakley")

    assert retrieved is not None
    assert retrieved.name == "Randy J. Oakley"


def test_leader_exists(sample_leader):
    """Test checking leader existence."""
    assert not leader_exists("randolph-oakley")

    create_or_update_leader(sample_leader)

    assert leader_exists("randolph-oakley")


# Place Tests

def test_create_place(sample_place):
    """Test creating a place."""
    ref = create_or_update_place(sample_place)

    assert ref.id == "ski-resorts-nordic-centers_snoqualmie-summit-ski-areas"
    assert place_exists("ski-resorts-nordic-centers_snoqualmie-summit-ski-areas")


def test_get_place(sample_place):
    """Test retrieving a place."""
    create_or_update_place(sample_place)

    retrieved = get_place("ski-resorts-nordic-centers_snoqualmie-summit-ski-areas")

    assert retrieved is not None
    assert retrieved.name == "Snoqualmie Summit Ski Areas"
    assert retrieved.place_permalink == sample_place.place_permalink
    assert retrieved.document_id == "ski-resorts-nordic-centers_snoqualmie-summit-ski-areas"


def test_get_nonexistent_place():
    """Test retrieving a nonexistent place."""
    retrieved = get_place("nonexistent")

    assert retrieved is None


def test_update_place(sample_place):
    """Test updating a place."""
    create_or_update_place(sample_place)

    # Update the place
    sample_place.name = "Snoqualmie Pass Ski Areas"
    create_or_update_place(sample_place)

    retrieved = get_place("ski-resorts-nordic-centers_snoqualmie-summit-ski-areas")

    assert retrieved is not None
    assert retrieved.name == "Snoqualmie Pass Ski Areas"


def test_place_exists(sample_place):
    """Test checking place existence."""
    doc_id = "ski-resorts-nordic-centers_snoqualmie-summit-ski-areas"

    assert not place_exists(doc_id)

    create_or_update_place(sample_place)

    assert place_exists(doc_id)


# Activity Tests

def test_create_activity(sample_activity):
    """Test creating an activity."""
    # First create leader and place
    create_or_update_leader(sample_activity.leader)
    create_or_update_place(sample_activity.place)

    ref = create_activity(sample_activity)

    assert ref.id == "backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10"
    assert activity_exists("backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10")


def test_create_duplicate_activity_fails(sample_activity):
    """Test that creating a duplicate activity raises an error."""
    # First create leader and place
    create_or_update_leader(sample_activity.leader)
    create_or_update_place(sample_activity.place)

    create_activity(sample_activity)

    with pytest.raises(ValueError, match="already exists"):
        create_activity(sample_activity)


def test_get_activity(sample_activity):
    """Test retrieving an activity with populated leader and place."""
    # First create leader and place
    create_or_update_leader(sample_activity.leader)
    create_or_update_place(sample_activity.place)

    create_activity(sample_activity)

    retrieved = get_activity("backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10")

    assert retrieved is not None
    assert retrieved.title == "Backcountry Ski/Snowboard - Snoqualmie Summit West"
    assert retrieved.description == sample_activity.description
    assert retrieved.difficulty_rating == ["M1 Intermediate Ski"]
    assert retrieved.activity_date == sample_activity.activity_date
    assert retrieved.discord_message_id is None

    # Check leader
    assert retrieved.leader.name == "Randy Oakley"
    assert retrieved.leader.document_id == "randolph-oakley"

    # Check place
    assert retrieved.place.name == "Snoqualmie Summit Ski Areas"
    assert retrieved.place.document_id == "ski-resorts-nordic-centers_snoqualmie-summit-ski-areas"


def test_get_nonexistent_activity():
    """Test retrieving a nonexistent activity."""
    retrieved = get_activity("nonexistent")

    assert retrieved is None


def test_update_activity(sample_activity):
    """Test updating an activity."""
    # First create leader and place
    create_or_update_leader(sample_activity.leader)
    create_or_update_place(sample_activity.place)

    create_activity(sample_activity)

    # Update the activity
    sample_activity.description = "Updated description"
    update_activity(sample_activity)

    retrieved = get_activity("backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10")

    assert retrieved is not None
    assert retrieved.description == "Updated description"


def test_update_nonexistent_activity_fails(sample_activity):
    """Test that updating a nonexistent activity raises an error."""
    with pytest.raises(ValueError, match="does not exist"):
        update_activity(sample_activity)


def test_update_discord_message_id(sample_activity):
    """Test updating the discord_message_id field."""
    # First create leader and place
    create_or_update_leader(sample_activity.leader)
    create_or_update_place(sample_activity.place)

    create_activity(sample_activity)

    # Update discord_message_id
    update_discord_message_id("backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10", "1234567890")

    retrieved = get_activity("backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10")

    assert retrieved is not None
    assert retrieved.discord_message_id == "1234567890"


def test_update_discord_message_id_nonexistent_fails():
    """Test that updating discord_message_id for nonexistent activity fails."""
    with pytest.raises(ValueError, match="does not exist"):
        update_discord_message_id("nonexistent", "1234567890")


def test_activity_exists(sample_activity):
    """Test checking activity existence."""
    doc_id = "backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10"

    assert not activity_exists(doc_id)

    # First create leader and place
    create_or_update_leader(sample_activity.leader)
    create_or_update_place(sample_activity.place)

    create_activity(sample_activity)

    assert activity_exists(doc_id)
