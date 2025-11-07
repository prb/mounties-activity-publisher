"""Searcher Cloud Function - fetches search results and enqueues scraper tasks."""

import logging
from typing import Dict, Any

from ..http_client import fetch_search_results
from ..parsers import parse_search_results
from ..tasks import enqueue_scrape_task, enqueue_search_task


logger = logging.getLogger(__name__)


def searcher_handler(request_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a search task - fetch search results and enqueue scraper tasks.

    This function:
    1. Fetches search results from the Mountaineers website
    2. Extracts activity detail URLs
    3. Enqueues a scraper task for each URL
    4. If there's a next page, enqueues another search task

    Args:
        request_json: Dict with:
            - start_index: int (required) - Starting index for pagination
            - activity_type: str (optional) - Activity type to search for

    Returns:
        Dict with:
            - status: str - "success" or "error"
            - activities_found: int - Number of activities found
            - has_next_page: bool - Whether there's a next page
            - error: str (optional) - Error message if status is "error"

    Example:
        >>> result = searcher_handler({'start_index': 0})
        >>> result['status']
        'success'
        >>> result['activities_found'] > 0
        True
    """
    try:
        # Extract parameters
        start_index = request_json.get('start_index', 0)
        activity_type = request_json.get('activity_type', 'Backcountry Skiing')

        logger.info(f"Searching for {activity_type} activities starting at index {start_index}")

        # Fetch search results
        html = fetch_search_results(start_index=start_index, activity_type=activity_type)

        # Parse search results
        activity_urls, next_page_url = parse_search_results(html)

        logger.info(f"Found {len(activity_urls)} activities")

        # Enqueue scraper tasks for each activity
        for url in activity_urls:
            try:
                enqueue_scrape_task(url)
                logger.debug(f"Enqueued scraper task for: {url}")
            except Exception as e:
                logger.error(f"Failed to enqueue scraper task for {url}: {e}")
                # Continue with other URLs even if one fails

        # If there's a next page, enqueue another search task
        if next_page_url:
            logger.info(f"Next page found, enqueueing search task")
            # Calculate next start index (increment by 20, the page size)
            next_start_index = start_index + 20
            try:
                enqueue_search_task(next_start_index, activity_type)
            except Exception as e:
                logger.error(f"Failed to enqueue next search task: {e}")

        return {
            'status': 'success',
            'activities_found': len(activity_urls),
            'has_next_page': next_page_url is not None,
        }

    except Exception as e:
        logger.error(f"Error in searcher_handler: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }
