"""Tests for activity retention: expire_at on writes and the backfill script."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from hypothesis import given, strategies as st

from scripts.backfill_expire_at import backfill
from src.db import activities
from src.db.activities import ACTIVITY_RETENTION_DAYS, compute_expire_at, create_activity, update_activity
from src.models import Activity, Leader

ACTIVITY_DATE = datetime(2026, 2, 10, 8, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def activity() -> Activity:
    return Activity(
        activity_permalink="https://www.mountaineers.org/activities/activities/x-2026-02-10",
        title="Backcountry Ski",
        description="desc",
        difficulty_rating=["M1 Intermediate Ski"],
        activity_date=ACTIVITY_DATE,
        leader=Leader(leader_permalink="https://www.mountaineers.org/members/jane-doe", name="Jane Doe"),
        place_name="Snoqualmie",
    )


@given(st.datetimes(min_value=datetime(2000, 1, 1), max_value=datetime(2100, 1, 1), timezones=st.just(timezone.utc)))
def test_expire_at_is_retention_days_after_activity_date(activity_date: datetime) -> None:
    assert compute_expire_at(activity_date) - activity_date == timedelta(days=ACTIVITY_RETENTION_DAYS)


def test_default_retention_is_one_year() -> None:
    assert ACTIVITY_RETENTION_DAYS == 365


def test_retention_days_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(activities, 'ACTIVITY_RETENTION_DAYS', 30)
    assert compute_expire_at(ACTIVITY_DATE) == ACTIVITY_DATE + timedelta(days=30)


def test_create_activity_writes_expire_at(mocker, activity: Activity) -> None:
    db = mocker.patch('src.db.activities.get_firestore_client').return_value
    doc_ref = db.collection.return_value.document.return_value

    create_activity(activity)

    written = doc_ref.set.call_args.args[0]
    assert written['expire_at'] == compute_expire_at(ACTIVITY_DATE)


def test_update_activity_keeps_expire_at(mocker, activity: Activity) -> None:
    """update_activity overwrites the document, so it must also write expire_at."""
    db = mocker.patch('src.db.activities.get_firestore_client').return_value
    mocker.patch('src.db.activities.activity_exists', return_value=True)
    doc_ref = db.collection.return_value.document.return_value

    update_activity(activity)

    written = doc_ref.set.call_args.args[0]
    assert written['expire_at'] == compute_expire_at(ACTIVITY_DATE)


def _doc(doc_id: str, data: dict) -> MagicMock:
    doc = MagicMock()
    doc.id = doc_id
    doc.to_dict.return_value = data
    doc.reference = f"ref-{doc_id}"
    return doc


def _client_with(docs: list[MagicMock]) -> MagicMock:
    client = MagicMock()
    client.collection.return_value.stream.return_value = docs
    return client


def test_backfill_dry_run_writes_nothing() -> None:
    client = _client_with([_doc('a', {'activity_date': ACTIVITY_DATE})])

    assert backfill(client, apply=False) == (1, 1)

    client.batch.return_value.update.assert_not_called()
    client.batch.return_value.commit.assert_not_called()


def test_backfill_apply_updates_only_documents_missing_expire_at() -> None:
    existing_expiry = datetime(2027, 2, 10, tzinfo=timezone.utc)
    client = _client_with([
        _doc('missing', {'activity_date': ACTIVITY_DATE}),
        _doc('has-expiry', {'activity_date': ACTIVITY_DATE, 'expire_at': existing_expiry}),
        _doc('no-date', {}),
    ])

    assert backfill(client, apply=True) == (3, 1)

    batch = client.batch.return_value
    batch.update.assert_called_once_with('ref-missing', {'expire_at': compute_expire_at(ACTIVITY_DATE)})
    batch.commit.assert_called_once()
