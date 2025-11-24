"""Detail Scraper Cloud Function - fetches activity details and stores in Firestore."""

import logging
from typing import Dict, Any
from datetime import datetime, timezone

from ..http_client import fetch_page
from ..parsers import parse_activity_detail
from ..db import (
    create_activity,
    create_or_update_leader,
    create_or_update_place,
    get_transaction,
    update_scrape_status,
)
from ..tasks import enqueue_publish_task
from ..config import is_processing_enabled


logger = logging.getLogger(__name__)


def scraper_handler(activity_url: str = None) -> Dict[str, Any]:
    """
    Handle a scrape task - fetch activity detail page and store in Firestore.

    This function:
    1. Checks if activity already exists in Firestore (skip if so)
    2. Fetches the activity detail page
    3. Parses all fields (title, description, date, leader, place, etc.)
    4. Creates/updates leader document in Firestore
    5. Creates/updates place document in Firestore
    6. Creates activity document in Firestore
    7. Enqueues a publish task to send to Discord

    Args:
        activity_url: URL of activity detail page.

    Returns:
        Dict with:
            - status: str - "success", "skipped", or "error"
            - activity_id: str (optional) - Document ID of created activity
            - reason: str (optional) - Reason for skipping
            - error: str (optional) - Error message if status is "error"

    Example:
        >>> result = scraper_handler(
        ...     activity_url='https://www.mountaineers.org/activities/activities/some-activity'
        ... )
        >>> result['status'] in ['success', 'skipped', 'error']
        True
    """
    try:
        # Check if processing is enabled
        if not is_processing_enabled():
            logger.info("Processing is disabled, skipping scrape task")
            return {
                'status': 'skipped',
                'reason': 'Processing is currently disabled',
            }

        if not activity_url:
            return {
                'status': 'error',
                'error': 'Missing required parameter: activity_url',
            }

        logger.info(f"Scraping activity: {activity_url}")

        # Extract document ID from URL (final path segment)
        activity_id = activity_url.rstrip('/').split('/')[-1]

        # Fetch activity detail page
        html = fetch_page(activity_url)

        # Parse activity details
        activity = parse_activity_detail(html, activity_url)

        logger.info(f"Parsed activity: {activity.title}")

        # Create/update leader and place documents
        leader_id = create_or_update_leader(activity.leader)
        place_id = create_or_update_place(activity.place)

        # Create activity document
        activity_ref = create_activity(activity)
        result_activity_id = activity_ref.id

        logger.info(f"Successfully created activity {result_activity_id}")

        # Enqueue publish task
        try:
            enqueue_publish_task(result_activity_id)
            logger.info(f"Enqueued publish task for activity {result_activity_id}")
        except Exception as e:
            logger.error(f"Failed to enqueue publish task: {e}")
            # Continue - activity is created, publish can be retried via catchup

        # Update bookkeeping status
        update_scrape_status("Green", success=True)

        return {
            'status': 'success',
            'activity_id': result_activity_id,
        }

    except Exception as e:
        logger.error(f"Error in scraper_handler: {e}", exc_info=True)

        # Update bookkeeping status
        error_message = str(e)
        update_scrape_status(f"Red: {error_message}")

        return {
            'status': 'error',
            'error': error_message,
        }
