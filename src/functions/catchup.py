"""Publishing Catchup Cloud Function - retries failed/missed publications."""

import logging
from typing import Dict, Any

from ..db import get_unpublished_activity_ids
from ..tasks import enqueue_publish_task


logger = logging.getLogger(__name__)


def publishing_catchup_handler() -> Dict[str, Any]:
    """
    Handle publishing catchup - find unpublished activities and enqueue publish tasks.

    This function:
    1. Queries Firestore for activities without discord_message_id
    2. Enqueues a publish task for each unpublished activity

    Args:
        None

    Returns:
        Dict with:
            - status: str - "success" or "error"
            - activities_found: int - Number of unpublished activities found
            - tasks_enqueued: int - Number of publish tasks successfully enqueued
            - error: str (optional) - Error message if status is "error"

    Example:
        >>> result = publishing_catchup_handler()
        >>> result['status']
        'success'
        >>> result['activities_found'] >= 0
        True
    """
    try:
        logger.info("Starting publishing catchup...")

        # Get all unpublished activity IDs
        activity_ids = get_unpublished_activity_ids()
        logger.info(f"Found {len(activity_ids)} unpublished activities")

        # Enqueue publish tasks
        tasks_enqueued = 0
        for activity_id in activity_ids:
            try:
                enqueue_publish_task(activity_id)
                logger.debug(f"Enqueued publish task for: {activity_id}")
                tasks_enqueued += 1
            except Exception as e:
                logger.error(f"Failed to enqueue publish task for {activity_id}: {e}")
                # Continue with other activities even if one fails

        logger.info(f"Publishing catchup complete: enqueued {tasks_enqueued}/{len(activity_ids)} tasks")

        return {
            'status': 'success',
            'activities_found': len(activity_ids),
            'tasks_enqueued': tasks_enqueued,
        }

    except Exception as e:
        logger.error(f"Error in publishing_catchup_handler: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }
