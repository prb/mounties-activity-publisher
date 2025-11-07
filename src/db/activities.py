"""Activity collection operations."""

from typing import Optional
from google.cloud.firestore_v1 import DocumentReference

from ..models import Activity, Leader, Place
from .firestore_client import get_firestore_client
from .leaders import get_leader
from .places import get_place


COLLECTION_NAME = 'activities'


def create_activity(activity: Activity) -> DocumentReference:
    """
    Create an activity document in Firestore.

    Note: This assumes leader and place documents already exist.

    Args:
        activity: Activity object to store

    Returns:
        DocumentReference for the created activity

    Raises:
        ValueError: If activity already exists

    Example:
        >>> activity = Activity(...)
        >>> ref = create_activity(activity)
        >>> ref.id
        'backcountry-ski-snoqualmie-2026-02-10'
    """
    db = get_firestore_client()
    doc_id = activity.document_id

    # Check if already exists
    if activity_exists(doc_id):
        raise ValueError(f"Activity {doc_id} already exists")

    # Create references to leader and place
    leader_ref = db.collection('leaders').document(activity.leader.document_id)
    place_ref = db.collection('places').document(activity.place.document_id)

    doc_ref = db.collection(COLLECTION_NAME).document(doc_id)

    # Build data dict and omit None values
    data = {
        'activity_permalink': activity.activity_permalink,
        'title': activity.title,
        'description': activity.description,
        'difficulty_rating': activity.difficulty_rating,
        'activity_date': activity.activity_date,
        'leader_ref': leader_ref,
        'place_ref': place_ref,
        'discord_message_id': activity.discord_message_id,
    }
    # Remove keys with None values
    data = {k: v for k, v in data.items() if v is not None}

    doc_ref.set(data)

    return doc_ref


def update_activity(activity: Activity) -> DocumentReference:
    """
    Update an existing activity document in Firestore.

    Args:
        activity: Activity object with updated data

    Returns:
        DocumentReference for the updated activity

    Raises:
        ValueError: If activity doesn't exist

    Example:
        >>> activity.description = "Updated description"
        >>> ref = update_activity(activity)
    """
    db = get_firestore_client()
    doc_id = activity.document_id

    # Check if exists
    if not activity_exists(doc_id):
        raise ValueError(f"Activity {doc_id} does not exist")

    # Create references to leader and place
    leader_ref = db.collection('leaders').document(activity.leader.document_id)
    place_ref = db.collection('places').document(activity.place.document_id)

    doc_ref = db.collection(COLLECTION_NAME).document(doc_id)

    # Build data dict and omit None values
    data = {
        'activity_permalink': activity.activity_permalink,
        'title': activity.title,
        'description': activity.description,
        'difficulty_rating': activity.difficulty_rating,
        'activity_date': activity.activity_date,
        'leader_ref': leader_ref,
        'place_ref': place_ref,
        'discord_message_id': activity.discord_message_id,
    }
    # Remove keys with None values
    data = {k: v for k, v in data.items() if v is not None}

    doc_ref.set(data)

    return doc_ref


def get_activity(document_id: str) -> Optional[Activity]:
    """
    Get an activity by document ID, including referenced leader and place.

    Args:
        document_id: The document ID (e.g., 'backcountry-ski-snoqualmie-2026-02-10')

    Returns:
        Activity object if found (with leader and place populated), None otherwise

    Example:
        >>> activity = get_activity('backcountry-ski-snoqualmie-2026-02-10')
        >>> activity.leader.name if activity else None
        'Randy Oakley'
    """
    db = get_firestore_client()
    doc_ref = db.collection(COLLECTION_NAME).document(document_id)
    doc = doc_ref.get()

    if not doc.exists:
        return None

    data = doc.to_dict()

    # Fetch referenced leader and place
    leader_ref = data['leader_ref']
    place_ref = data['place_ref']

    leader = get_leader(leader_ref.id)
    place = get_place(place_ref.id)

    if not leader or not place:
        # Referenced documents missing - should not happen
        raise ValueError(f"Activity {document_id} has missing leader or place reference")

    return Activity(
        activity_permalink=data['activity_permalink'],
        title=data['title'],
        description=data['description'],
        difficulty_rating=data['difficulty_rating'],
        activity_date=data['activity_date'],
        leader=leader,
        place=place,
        discord_message_id=data.get('discord_message_id'),
    )


def activity_exists(document_id: str) -> bool:
    """
    Check if an activity document exists.

    Args:
        document_id: The document ID to check

    Returns:
        True if activity exists, False otherwise

    Example:
        >>> activity_exists('backcountry-ski-snoqualmie-2026-02-10')
        True
    """
    db = get_firestore_client()
    doc_ref = db.collection(COLLECTION_NAME).document(document_id)
    return doc_ref.get().exists


def update_discord_message_id(document_id: str, message_id: str) -> None:
    """
    Update the discord_message_id field for an activity.

    Args:
        document_id: The activity document ID
        message_id: The Discord message ID

    Raises:
        ValueError: If activity doesn't exist

    Example:
        >>> update_discord_message_id('backcountry-ski-snoqualmie-2026-02-10', '1234567890')
    """
    db = get_firestore_client()
    doc_ref = db.collection(COLLECTION_NAME).document(document_id)

    if not doc_ref.get().exists:
        raise ValueError(f"Activity {document_id} does not exist")

    doc_ref.update({'discord_message_id': message_id})
