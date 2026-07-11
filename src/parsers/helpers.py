"""Shared parsing helpers used by both the detail and listing parsers."""

from datetime import datetime
import pytz


# Range separators used for multi-day activities. We only publish the start
# date, so we split on the first one we find.
_DATE_RANGE_SEPARATORS = ("—", "–", " - ")

_PACIFIC = pytz.timezone('America/Los_Angeles')


def parse_activity_date(date_str: str) -> datetime:
    """
    Parse an activity date string and convert from Pacific time to UTC.

    Handles:
      - Internal whitespace (single-digit days render as "Jul  3" with a double
        space); collapsed before parsing.
      - Multi-day activities (e.g. "Wed, Feb 11, 2026 — Thu, Feb 12, 2026"); the
        start date is used.

    Format: ``%a, %b %d, %Y`` (e.g., "Tue, Feb 10, 2026").

    Args:
        date_str: Raw date string extracted from the page.

    Returns:
        The start date as a timezone-aware UTC datetime.

    Raises:
        ValueError: If the string is empty or cannot be parsed.
    """
    if not date_str or not date_str.strip():
        raise ValueError("Could not find activity date")

    # Collapse all internal/leading/trailing whitespace to single spaces.
    normalized = ' '.join(date_str.split())

    # For multi-day activities, keep only the start date.
    for separator in _DATE_RANGE_SEPARATORS:
        if separator in normalized:
            normalized = normalized.split(separator, 1)[0].strip()
            break

    naive_date = datetime.strptime(normalized, "%a, %b %d, %Y")

    # Localize to Pacific time, then convert to UTC.
    pacific_date = _PACIFIC.localize(naive_date)
    return pacific_date.astimezone(pytz.UTC)


def parse_difficulty_rating(text: str) -> list[str]:
    """
    Parse a difficulty string into a normalized list of ratings.

    Strips an optional "Difficulty:" prefix, splits on commas, and collapses
    internal whitespace within each rating.

    Args:
        text: Raw difficulty text (may include the "Difficulty:" label).

    Returns:
        List of difficulty ratings (empty if none).
    """
    if not text:
        return []

    full_text = text.strip()

    # Remove "Difficulty:" prefix if present.
    if full_text.startswith("Difficulty:"):
        full_text = full_text[len("Difficulty:"):].strip()

    # Split by comma and collapse whitespace within each rating.
    return [' '.join(r.split()) for r in full_text.split(',') if r.strip()]
