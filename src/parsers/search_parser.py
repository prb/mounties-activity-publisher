"""Parser for Mountaineers search results pages."""

from lxml import html, etree
from typing import Optional


def parse_search_results(html_content: str) -> tuple[list[str], Optional[str]]:
    """
    Parse search results HTML and extract activity URLs and next page URL.

    Args:
        html_content: Raw HTML content from search results page

    Returns:
        Tuple of (list of activity URLs, next page URL or None)

    Example:
        >>> html = '<html>...</html>'
        >>> activity_urls, next_url = parse_search_results(html)
        >>> len(activity_urls) > 0
        True
    """
    activity_urls = extract_activity_urls(html_content)
    next_page_url = extract_next_page_url(html_content)
    return activity_urls, next_page_url


def extract_activity_urls(html_content: str) -> list[str]:
    """
    Extract activity detail URLs from search results.

    Uses XPath: //div[contains(@class, 'result-item')] to find each result,
    then .//h3[@class='result-title']/a/@href for the URL.

    Args:
        html_content: Raw HTML content from search results page

    Returns:
        List of activity detail URLs

    Example:
        >>> html = '<div class="result-item"><h3 class="result-title"><a href="https://example.com/activity-1">Activity</a></h3></div>'
        >>> urls = extract_activity_urls(html)
        >>> len(urls)
        1
    """
    if not html_content or not html_content.strip():
        return []

    try:
        tree = html.fromstring(html_content)
    except Exception:
        return []

    # Find all result items (using contains since class may have multiple values)
    result_items = tree.xpath("//div[contains(@class, 'result-item')]")

    activity_urls = []
    for item in result_items:
        # Extract the activity URL from each result item
        urls = item.xpath(".//h3[@class='result-title']/a/@href")
        if urls:
            activity_urls.append(urls[0])

    return activity_urls


def extract_next_page_url(html_content: str) -> Optional[str]:
    """
    Extract the "next page" URL from pagination, if present.

    Uses XPath: //nav[@class='pagination']//li[@class='next']/a/@href

    Args:
        html_content: Raw HTML content from search results page

    Returns:
        Next page URL if present, None otherwise

    Example:
        >>> html = '<nav class="pagination"><ul><li class="next"><a href="/page2">Next</a></li></ul></nav>'
        >>> url = extract_next_page_url(html)
        >>> url is not None
        True
    """
    if not html_content or not html_content.strip():
        return None

    try:
        tree = html.fromstring(html_content)
    except Exception:
        return None

    # Look for next page link
    next_urls = tree.xpath("//nav[@class='pagination']//li[@class='next']/a/@href")

    return next_urls[0] if next_urls else None
