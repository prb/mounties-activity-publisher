"""Firestore database operations."""

from .firestore_client import get_firestore_client, initialize_firebase
from .leaders import create_or_update_leader, get_leader, leader_exists
from .places import create_or_update_place, get_place, place_exists
from .activities import (
    create_activity,
    get_activity,
    update_activity,
    activity_exists,
    update_discord_message_id,
)

__all__ = [
    # Client
    'get_firestore_client',
    'initialize_firebase',
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
]
