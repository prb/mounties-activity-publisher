"""Searcher Cloud Function - fetches search results and enqueues scraper tasks."""

import logging
from typing import Dict, Any
from datetime import datetime, timezone

from ..db import activity_exists
from ..http_client import fetch_search_results
from ..parsers import parse_search_results
from ..tasks import enqueue_scrape_task, enqueue_search_task
from ..config import is_processing_enabled


logger = logging.getLogger(__name__)


def searcher_handler(start_index: int = 0, activity_type: str = 'Backcountry Skiing') -> Dict[str, Any]:
    """
    Handle a search task - fetch search results and enqueue scraper tasks.

    This function:
    1. Fetches search results from the Mountaineers website
    2. Extracts activity detail URLs
    3. Checks if activity already exists in Firestore
    4. Enqueues a scraper task for each NEW activity
    5. If there's a next page, enqueues another search task

    Args:
        start_index: Starting index for pagination.
        activity_type: Activity type to search for.

    Returns:
        Dict with:
            - status: str - "success" or "error"
            - activities_found: int - Number of activities found
            - new_activities: int - Number of new activities enqueued
            - has_next_page: bool - Whether there's a next page
            - error: str (optional) - Error message if status is "error"

    Example:
        >>> result = searcher_handler(start_index=0)
        >>> result['status']
        'success'
        >>> result['activities_found'] > 0
        True
    """
    try:
        # Check if processing is enabled
        if not is_processing_enabled():
            logger.info("Processing is disabled, skipping search task")
            return {
                'status': 'skipped',
                'reason': 'Processing is currently disabled',
            }

        logger.info(f"Searching for {activity_type} activities starting at index {start_index}")

        # Fetch search results
        html = fetch_search_results(start_index=start_index, activity_type=activity_type)

        # Parse search results
        activity_urls, next_page_url = parse_search_results(html)


        logger.info(f"Found {len(activity_urls)} activities")

        # Enqueue scraper tasks for each NEW activity
        new_activities_count = 0
        for url in activity_urls:
            try:
                # Extract document ID from URL (final path segment)
                # e.g. https://www.mountaineers.org/activities/activities/backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10
                doc_id = url.rstrip('/').split('/')[-1]

                if activity_exists(doc_id):
                    logger.debug(f"Activity {doc_id} already exists, skipping scrape")
                    continue

                enqueue_scrape_task(url)
                logger.debug(f"Enqueued scraper task for: {url}")
                new_activities_count += 1
            except Exception as e:
                logger.error(f"Failed to enqueue scraper task for {url}: {e}")
                # Continue with other URLs even if one fails

        logger.info(f"Enqueued {new_activities_count} new activities for scraping")

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

        # Update bookkeeping status
        error_message = str(e)

        return {
            'status': 'error',
            'error': error_message,
        }
