"""HTTP client for fetching Mountaineers website pages."""

import os
import uuid
import logging
import requests
from urllib.parse import urlencode


logger = logging.getLogger(__name__)


# Version is set via environment variable or defaults to "dev"
# In production, this should be the Git SHA
VERSION = os.environ.get('APP_VERSION', 'dev')
USER_AGENT = f'mounties-activities-discord-publisher/{VERSION}'

# Default timeout for requests (in seconds)
DEFAULT_TIMEOUT = 30

# The Mountaineers has implemented Cloudflare scraper protection. A custom
# bypass rule allows access to this specific listing URL (and its faceted-query
# child path) when a custom header is present. See issue #31.
APPROVED_URL = 'https://www.mountaineers.org/volunteer/volunteer-with-us/find-all-volunteer-activities'
FACETED_QUERY_URL = f'{APPROVED_URL}/@@faceted_query'

# Header that identifies us to the bypass rule. The value is sourced from the
# environment (Secret Manager in production) and must never be logged. A default
# is provided so the app works before the secret is wired up.
SCRAPER_HEADER_NAME = 'mtn-approved-scraper'
SCRAPER_HEADER_VALUE = os.environ.get('MTN_SCRAPER_HEADER_VALUE', 'MountaineersDevRequest')


def _is_approved_url(url: str) -> bool:
    """Return True if the URL is under the approved listing path (so the bypass
    header, cache-control, and cache-buster should be applied)."""
    return url.startswith(APPROVED_URL)


def fetch_page(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """
    Fetch a web page with proper User-Agent header.

    Requests under the approved listing URL automatically receive the
    Cloudflare bypass header plus cache-busting (see issue #31); all other
    requests are sent with just the User-Agent.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds (default: 30)

    Returns:
        HTML content as string

    Raises:
        requests.exceptions.RequestException: If the request fails

    Example:
        >>> html = fetch_page('https://www.mountaineers.org/activities/activities')
        >>> len(html) > 0
        True
    """
    headers = {
        'User-Agent': USER_AGENT,
    }

    if _is_approved_url(url):
        # Attach the Cloudflare bypass header. Never log its value.
        headers[SCRAPER_HEADER_NAME] = SCRAPER_HEADER_VALUE
        # Responses are served through Varnish and a stale (often empty) page
        # can be returned after a new activity is listed. Force a fresh copy
        # with both no-cache and a unique cache-buster query param.
        headers['Cache-Control'] = 'no-cache'
        separator = '&' if '?' in url else '?'
        url = f"{url}{separator}_cb={uuid.uuid4().hex}"

    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    return response.text


def fetch_search_results(start_index: int = 0, activity_type: str = 'Backcountry Skiing') -> str:
    """
    Fetch activity listing results from the approved faceted-query endpoint.

    The approved listing page itself is a JS shell; results load via this AJAX
    endpoint. The activity-type facet on this page is ``c4`` (values use spaces).

    Args:
        start_index: Zero-based record number to start at (default: 0)
        activity_type: Type of activity to search for (default: 'Backcountry Skiing')

    Returns:
        HTML content as string

    Raises:
        requests.exceptions.RequestException: If the request fails

    Example:
        >>> html = fetch_search_results(start_index=0)
        >>> 'result-item' in html
        True
    """
    params = {
        'c4[]': activity_type,
        'b_start:int': start_index,
    }

    # Keep '[]' and ':' literal so the URL matches the documented facet format
    # (e.g. c4[]=Backcountry+Skiing&b_start:int=0).
    url = f"{FACETED_QUERY_URL}?{urlencode(params, safe='[]:')}"

    # Log the base URL without the cache-buster/header (added inside fetch_page).
    logger.info(f"Fetching activity listing (start_index={start_index}, activity_type={activity_type})")

    return fetch_page(url)
