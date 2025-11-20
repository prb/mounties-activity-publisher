"""Detail Scraper Cloud Function - fetches activity details and stores in Firestore."""

import logging
from typing import Dict, Any
from datetime import datetime, timezone

from ..http_client import fetch_page
from ..parsers import parse_activity_detail
from ..db import (
    activity_exists,
    create_activity,
    create_or_update_leader,
    create_or_update_place,
    get_transaction,
)
from ..tasks import enqueue_publish_task


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
            # Still consider this a success for bookkeeping purposes
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

        # Create activity in Firestore using a transaction
        from google.cloud import firestore

        @firestore.transactional
        def create_activity_transactional(transaction, activity_obj):
            return create_activity(activity_obj, transaction=transaction)

        transaction = get_transaction()
        try:
            activity_ref = create_activity_transactional(transaction, activity)
            logger.info(f"Created activity: {activity_ref.id}")
            
            # Enqueue publish task
            try:
                enqueue_publish_task(activity_ref.id)
                logger.info(f"Enqueued publish task for: {activity_ref.id}")
            except Exception as e:
                logger.error(f"Failed to enqueue publish task: {e}")
                # Don't fail the scraper if publish enqueueing fails
                # The activity is already in Firestore

            status = 'success'
            result_activity_id = activity_ref.id

        except ValueError as e:
            # This catches the "Activity already exists" error raised by create_activity
            if "already exists" in str(e):
                logger.info(f"Activity {activity.document_id} already exists (race condition handled), skipping")
                status = 'skipped'
                result_activity_id = activity.document_id
            else:
                raise e



        if status == 'skipped':
            return {
                'status': 'skipped',
                'activity_id': result_activity_id,
                'reason': 'Activity already exists in Firestore',
            }
        
        return {
            'status': 'success',
            'activity_id': result_activity_id,
        }

    except Exception as e:
        logger.error(f"Error in scraper_handler: {e}", exc_info=True)

        # Update bookkeeping status
        error_message = str(e)

        return {
            'status': 'error',
            'error': error_message,
        }
