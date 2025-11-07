"""HTTP client for fetching Mountaineers website pages."""

import os
import requests
from typing import Optional


# Version is set via environment variable or defaults to "dev"
# In production, this should be the Git SHA
VERSION = os.environ.get('APP_VERSION', 'dev')
USER_AGENT = f'mounties-activities-discord-publisher/{VERSION}'

# Default timeout for requests (in seconds)
DEFAULT_TIMEOUT = 30


def fetch_page(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """
    Fetch a web page with proper User-Agent header.

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

    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    return response.text


def fetch_search_results(start_index: int = 0, activity_type: str = 'Backcountry Skiing') -> str:
    """
    Fetch search results from Mountaineers website.

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
    from urllib.parse import urlencode

    base_url = 'https://www.mountaineers.org/activities/activities/@@faceted_query'

    # Build query parameters
    params = {
        'b_start:int': start_index,
        'c4[]': activity_type,
    }

    # Construct full URL
    url = f"{base_url}?{urlencode(params, safe='[]')}"

    return fetch_page(url)
