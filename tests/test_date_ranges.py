"""Tests for parsing single-day and multi-day activity dates (issues #9, #20)."""

import pytest
from lxml import html

from src.parsers.detail_parser import extract_activity_date


def _extract(date_text: str):
    """Run extract_activity_date against a minimal detail-page fragment."""
    tree = html.fromstring(
        "<html><body><div class='program-core'><ul class='details'>"
        f"<li>{date_text}</li></ul></div></body></html>"
    )
    return extract_activity_date(tree)


@pytest.mark.parametrize(
    "date_text",
    [
        "Wed, Feb 11, 2026 \u2014 Thu, Feb 12, 2026",  # em dash (issue #9)
        "Wed, Feb 11, 2026 - Thu, Feb 12, 2026",  # hyphen (issue #20)
        "Wed, Feb 11, 2026\n            \u2014 Thu, Feb 12, 2026",  # newline
    ],
)
def test_multi_day_range_uses_start_date(date_text: str) -> None:
    """A date range resolves to the same value as its first day alone."""
    assert _extract(date_text) == _extract("Wed, Feb 11, 2026")


def test_single_day_parses() -> None:
    assert _extract("Tue, Feb 10, 2026") is not None
