"""Firestore database operations."""

from .firestore_client import get_firestore_client, initialize_firebase, get_transaction
from .leaders import create_or_update_leader, get_leader, leader_exists
from .places import create_or_update_place, get_place, place_exists
from .activities import (
    create_activity,
    get_activity,
    update_activity,
    activity_exists,
    update_discord_message_id,
    get_unpublished_activity_ids,
)

__all__ = [
    # Client
    'get_firestore_client',
    'initialize_firebase',
    'get_transaction',
    # Leaders
    'create_or_update_leader',
    'get_leader',
    'leader_exists',
    # Places
    'create_or_update_place',
    'get_place',
    'place_exists',
    # Activities
    'create_activity',
    'get_activity',
    'update_activity',
    'activity_exists',
    'update_discord_message_id',
    'get_unpublished_activity_ids',
]
