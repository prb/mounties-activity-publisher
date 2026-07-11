"""Parser for the Mountaineers approved activity-listing (faceted-query) page.

Detail pages remain Cloudflare-protected, so everything we publish is built
from the ``result-item`` markup on the listing itself (single-pass). See issue
#31.
"""

import logging
from typing import Optional

from lxml import html

from ..models import Activity, Leader
from .helpers import parse_activity_date, parse_difficulty_rating


logger = logging.getLogger(__name__)

# Only rows whose permalink is under this path are real activities; the folder
# can also contain routes/places and other content with result-title links.
_ACTIVITY_PATH = '/activities/activities/'

# The listing renders the activity type with a trailing " Trip"
# (e.g. "Backcountry Skiing Trip"); the rest of the system keys on the bare
# type ("Backcountry Skiing"), e.g. for the Discord emoji lookup.
_TYPE_SUFFIX = ' Trip'


def parse_activity_listing(html_content: str) -> tuple[list[Activity], Optional[str]]:
    """
    Parse a faceted-query listing page into activities and the next-page URL.

    Args:
        html_content: Raw HTML from the ``@@faceted_query`` endpoint.

    Returns:
        Tuple of (list of Activity, next page URL or None). Rows that are not
        activities, or that are missing required fields, are skipped.
    """
    if not html_content or not html_content.strip():
        return [], None

    try:
        tree = html.fromstring(html_content)
    except Exception:
        logger.warning("Could not parse listing HTML")
        return [], None

    activities = []
    for item in tree.xpath("//div[contains(@class, 'result-item')]"):
        activity = _parse_result_item(item)
        if activity is not None:
            activities.append(activity)

    return activities, _extract_next_page_url(tree)


def _clean(nodes) -> str:
    """Join text nodes and collapse whitespace to single spaces."""
    return ' '.join(''.join(nodes).split())


def _parse_result_item(item) -> Optional[Activity]:
    """Build an Activity from a single result-item, or None if it should be
    skipped (non-activity row or missing required fields)."""
    hrefs = item.xpath(".//h3[@class='result-title']/a/@href")
    permalink = hrefs[0].strip() if hrefs else None

    # Skip non-activity rows (routes/places, etc.).
    if not permalink or _ACTIVITY_PATH not in permalink:
        return None

    title = _clean(item.xpath(".//h3[@class='result-title']/a/text()"))
    if not title:
        logger.warning(f"Skipping result-item with no title: {permalink}")
        return None

    # Leader is required; skip the row (rather than failing the whole page) if
    # it is missing.
    leader_names = item.xpath(".//div[@class='result-leader']//a/text()")
    leader_hrefs = item.xpath(".//div[@class='result-leader']//a/@href")
    if not leader_names or not leader_hrefs:
        logger.warning(f"Skipping activity with no leader: {permalink}")
        return None

    # Date is required.
    date_nodes = item.xpath(".//div[@class='result-date']/text()")
    try:
        activity_date = parse_activity_date(''.join(date_nodes))
    except ValueError as e:
        logger.warning(f"Skipping activity with unparseable date ({permalink}): {e}")
        return None

    leader = Leader(
        leader_permalink=leader_hrefs[0].strip(),
        name=leader_names[0].strip(),
    )

    return Activity(
        activity_permalink=permalink,
        title=title,
        description=_clean(item.xpath(".//div[@class='result-summary']/text()")),
        difficulty_rating=parse_difficulty_rating(''.join(item.xpath(".//div[@class='result-difficulty']/text()"))),
        activity_date=activity_date,
        place=None,
        place_name=_place_name_from_title(title),
        leader=leader,
        activity_type=_normalize_activity_type(item.xpath(".//div[@class='result-type']/text()")),
        branch=_clean(item.xpath(".//div[@class='result-branch']/text()")) or None,
    )


def _normalize_activity_type(nodes) -> Optional[str]:
    """Clean the result-type text and strip a trailing ' Trip' so it matches the
    bare type the rest of the system expects."""
    activity_type = _clean(nodes)
    if not activity_type:
        return None
    if activity_type.endswith(_TYPE_SUFFIX):
        activity_type = activity_type[:-len(_TYPE_SUFFIX)].strip()
    return activity_type or None


def _place_name_from_title(title: str) -> Optional[str]:
    """Recover the route/place name from the title (text after the first ' - ').

    The place permalink is only on the (unreachable) detail page, so we keep the
    name as plain text. Returns None when the title has no ' - ' separator.
    """
    if ' - ' not in title:
        return None
    name = title.split(' - ', 1)[1].strip()
    return name or None


def _extract_next_page_url(tree) -> Optional[str]:
    """Extract the next-page URL from pagination, if present.

    XPath: //nav[@class='pagination']//li[@class='next']/a/@href
    """
    next_urls = tree.xpath("//nav[@class='pagination']//li[@class='next']/a/@href")
    return next_urls[0] if next_urls else None
