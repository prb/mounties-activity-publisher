"""Searcher Cloud Function - single-pass listing scrape and publish enqueue.

Detail pages remain Cloudflare-protected, so the searcher builds each Activity
directly from the approved listing page (single-pass) and enqueues a publish
task for every new activity. The detail scraper (``scraper.py`` / ``scrape-queue``)
is kept dormant as a fallback / manual-reprocessing path. See issue #31.
"""

import logging
from typing import Dict, Any

from ..db import (
    activity_exists,
    create_activity,
    create_or_update_leader,
    create_or_update_place,
    update_search_status,
)
from ..http_client import fetch_search_results
from ..parsers import parse_activity_listing
from ..tasks import enqueue_publish_task, enqueue_search_task
from ..config import is_processing_enabled


logger = logging.getLogger(__name__)

# Listing page size; pagination advances b_start by this amount.
PAGE_SIZE = 20


def searcher_handler(start_index: int = 0, activity_type: str = 'Backcountry Skiing') -> Dict[str, Any]:
    """
    Handle a search task - fetch the listing, store new activities, and enqueue
    publish tasks.

    This function:
    1. Fetches the approved listing page for the activity type / page.
    2. Parses each result-item into a full Activity.
    3. Skips activities that already exist in Firestore.
    4. For each new activity: stores leader (+ place if present) and activity,
       then enqueues a publish task.
    5. If there's a next page, enqueues another search task.

    Args:
        start_index: Starting index for pagination.
        activity_type: Activity type to search for.

    Returns:
        Dict with:
            - status: str - "success", "skipped", or "error"
            - activities_found: int - Number of activities parsed from the page
            - new_activities: int - Number of new activities stored/enqueued
            - has_next_page: bool - Whether there's a next page
            - error: str (optional) - Error message if status is "error"
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

        # Fetch and parse the listing page
        html = fetch_search_results(start_index=start_index, activity_type=activity_type)
        activities, next_page_url = parse_activity_listing(html)

        logger.info(f"Found {len(activities)} activities")

        new_activities_count = 0
        for activity in activities:
            activity_id = activity.document_id

            # Skip activities we've already processed
            if activity_exists(activity_id):
                logger.debug(f"Activity {activity_id} already exists, skipping")
                continue

            try:
                _store_and_enqueue(activity)
                new_activities_count += 1
            except Exception as e:
                logger.error(f"Failed to store/enqueue activity {activity_id}: {e}", exc_info=True)

        logger.info(f"Stored {new_activities_count} new activities")

        # If there's a next page, enqueue another search task
        if next_page_url:
            logger.info("Next page found, enqueueing search task")
            try:
                enqueue_search_task(start_index + PAGE_SIZE, activity_type)
            except Exception as e:
                logger.error(f"Failed to enqueue next search task: {e}")

        # Update bookkeeping status
        update_search_status("Green", success=True)

        return {
            'status': 'success',
            'activities_found': len(activities),
            'new_activities': new_activities_count,
            'has_next_page': next_page_url is not None,
        }

    except Exception as e:
        logger.error(f"Error in searcher_handler: {e}", exc_info=True)

        # Update bookkeeping status
        error_message = str(e)
        update_search_status(f"Red: {error_message}")

        return {
            'status': 'error',
            'error': error_message,
        }


def _store_and_enqueue(activity) -> None:
    """Store leader (+ place if present) and activity, then enqueue a publish
    task. create_activity is idempotent, so a retry is safe."""
    create_or_update_leader(activity.leader)
    if activity.place is not None:
        create_or_update_place(activity.place)

    activity_ref = create_activity(activity)
    activity_id = activity_ref.id
    logger.info(f"Created activity {activity_id}")

    # Enqueue publish task. If this fails, the activity is still stored and can
    # be picked up by the catchup function.
    enqueue_publish_task(activity_id)
    logger.debug(f"Enqueued publish task for activity {activity_id}")
