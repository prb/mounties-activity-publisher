"""Detail Scraper Cloud Function - fetches activity details and stores in Firestore."""

import logging
from typing import Dict, Any

from ..http_client import fetch_page
from ..parsers import parse_activity_detail
from ..db import (
    activity_exists,
    create_activity,
    create_or_update_leader,
    create_or_update_place,
)
from ..tasks import enqueue_publish_task


logger = logging.getLogger(__name__)


def scraper_handler(request_json: Dict[str, Any]) -> Dict[str, Any]:
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
        request_json: Dict with:
            - activity_url: str (required) - URL of activity detail page

    Returns:
        Dict with:
            - status: str - "success", "skipped", or "error"
            - activity_id: str (optional) - Document ID of created activity
            - reason: str (optional) - Reason for skipping
            - error: str (optional) - Error message if status is "error"

    Example:
        >>> result = scraper_handler({
        ...     'activity_url': 'https://www.mountaineers.org/activities/activities/some-activity'
        ... })
        >>> result['status'] in ['success', 'skipped', 'error']
        True
    """
    try:
        # Extract parameters
        activity_url = request_json.get('activity_url')
        if not activity_url:
            return {
                'status': 'error',
                'error': 'Missing required parameter: activity_url',
            }

        logger.info(f"Scraping activity: {activity_url}")

        # Parse URL to get document ID
        activity_id = activity_url.rstrip('/').split('/')[-1]

        # Check if activity already exists
        if activity_exists(activity_id):
            logger.info(f"Activity {activity_id} already exists, skipping")
            return {
                'status': 'skipped',
                'activity_id': activity_id,
                'reason': 'Activity already exists in Firestore',
            }

        # Fetch activity detail page
        html = fetch_page(activity_url)

        # Parse activity details
        activity = parse_activity_detail(html, activity_url)

        logger.info(f"Parsed activity: {activity.title}")

        # Create/update leader in Firestore
        leader_ref = create_or_update_leader(activity.leader)
        logger.debug(f"Created/updated leader: {leader_ref.id}")

        # Create/update place in Firestore
        place_ref = create_or_update_place(activity.place)
        logger.debug(f"Created/updated place: {place_ref.id}")

        # Create activity in Firestore
        activity_ref = create_activity(activity)
        logger.info(f"Created activity: {activity_ref.id}")

        # Enqueue publish task
        try:
            enqueue_publish_task(activity_ref.id)
            logger.info(f"Enqueued publish task for: {activity_ref.id}")
        except Exception as e:
            logger.error(f"Failed to enqueue publish task: {e}")
            # Don't fail the scraper if publish enqueueing fails
            # The activity is already in Firestore

        return {
            'status': 'success',
            'activity_id': activity_ref.id,
        }

    except Exception as e:
        logger.error(f"Error in scraper_handler: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }
