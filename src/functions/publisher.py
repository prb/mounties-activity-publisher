"""Publisher Cloud Function - publishes activities to Discord."""

import logging
from typing import Dict, Any

from ..db import get_activity, update_discord_message_id
from ..discord_client import publish_activity_to_discord


logger = logging.getLogger(__name__)


def publisher_handler(request_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a publish task - send activity to Discord.

    This function:
    1. Retrieves the activity from Firestore by ID
    2. Checks if already published (has discord_message_id)
    3. Formats and sends message to Discord
    4. Updates activity with discord_message_id

    Args:
        request_json: Dict with:
            - activity_id: str (required) - Firestore document ID

    Returns:
        Dict with:
            - status: str - "success", "skipped", or "error"
            - message_id: str (optional) - Discord message ID
            - reason: str (optional) - Reason for skipping
            - error: str (optional) - Error message if status is "error"

    Example:
        >>> result = publisher_handler({
        ...     'activity_id': 'backcountry-ski-snoqualmie-2026-02-10'
        ... })
        >>> result['status'] in ['success', 'skipped', 'error']
        True
    """
    try:
        # Extract parameters
        activity_id = request_json.get('activity_id')
        if not activity_id:
            return {
                'status': 'error',
                'error': 'Missing required parameter: activity_id',
            }

        logger.info(f"Publishing activity: {activity_id}")

        # Get activity from Firestore
        activity = get_activity(activity_id)
        if not activity:
            return {
                'status': 'error',
                'error': f'Activity not found: {activity_id}',
            }

        # Check if already published
        if activity.discord_message_id:
            logger.info(f"Activity {activity_id} already published to Discord (message ID: {activity.discord_message_id}), skipping")
            return {
                'status': 'skipped',
                'message_id': activity.discord_message_id,
                'reason': 'Activity already published to Discord',
            }

        # Publish to Discord
        message_id = publish_activity_to_discord(activity)
        logger.info(f"Published activity {activity_id} to Discord (message ID: {message_id})")

        # Update activity with message ID
        update_discord_message_id(activity_id, message_id)
        logger.info(f"Updated activity {activity_id} with discord_message_id: {message_id}")

        return {
            'status': 'success',
            'message_id': message_id,
        }

    except Exception as e:
        logger.error(f"Error in publisher_handler: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }
