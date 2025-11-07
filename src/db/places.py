"""Place collection operations."""

from typing import Optional
from google.cloud.firestore_v1 import DocumentReference

from ..models import Place
from .firestore_client import get_firestore_client


COLLECTION_NAME = 'places'


def create_or_update_place(place: Place) -> DocumentReference:
    """
    Create or update a place document in Firestore.

    Args:
        place: Place object to store

    Returns:
        DocumentReference for the created/updated place

    Example:
        >>> place = Place(
        ...     place_permalink="https://www.mountaineers.org/activities/routes-places/cascades/mount-rainier",
        ...     name="Mount Rainier"
        ... )
        >>> ref = create_or_update_place(place)
        >>> ref.id
        'cascades_mount-rainier'
    """
    db = get_firestore_client()
    doc_id = place.document_id

    doc_ref = db.collection(COLLECTION_NAME).document(doc_id)

    # Build data dict and omit None values
    data = {
        'place_permalink': place.place_permalink,
        'name': place.name,
    }
    # Remove keys with None values
    data = {k: v for k, v in data.items() if v is not None}

    doc_ref.set(data)

    return doc_ref


def get_place(document_id: str) -> Optional[Place]:
    """
    Get a place by document ID.

    Args:
        document_id: The document ID (e.g., 'cascades_mount-rainier')

    Returns:
        Place object if found, None otherwise

    Example:
        >>> place = get_place('cascades_mount-rainier')
        >>> place.name if place else None
        'Mount Rainier'
    """
    db = get_firestore_client()
    doc_ref = db.collection(COLLECTION_NAME).document(document_id)
    doc = doc_ref.get()

    if not doc.exists:
        return None

    data = doc.to_dict()
    return Place(
        place_permalink=data['place_permalink'],
        name=data['name'],
    )


def place_exists(document_id: str) -> bool:
    """
    Check if a place document exists.

    Args:
        document_id: The document ID to check

    Returns:
        True if place exists, False otherwise

    Example:
        >>> place_exists('cascades_mount-rainier')
        True
    """
    db = get_firestore_client()
    doc_ref = db.collection(COLLECTION_NAME).document(document_id)
    return doc_ref.get().exists
