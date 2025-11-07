"""Leader collection operations."""

from typing import Optional
from google.cloud.firestore_v1 import DocumentReference

from ..models import Leader
from .firestore_client import get_firestore_client


COLLECTION_NAME = 'leaders'


def create_or_update_leader(leader: Leader) -> DocumentReference:
    """
    Create or update a leader document in Firestore.

    Args:
        leader: Leader object to store

    Returns:
        DocumentReference for the created/updated leader

    Example:
        >>> leader = Leader(
        ...     leader_permalink="https://www.mountaineers.org/members/john-doe",
        ...     name="John Doe"
        ... )
        >>> ref = create_or_update_leader(leader)
        >>> ref.id
        'john-doe'
    """
    db = get_firestore_client()
    doc_id = leader.document_id

    doc_ref = db.collection(COLLECTION_NAME).document(doc_id)

    # Build data dict and omit None values
    data = {
        'leader_permalink': leader.leader_permalink,
        'name': leader.name,
    }
    # Remove keys with None values
    data = {k: v for k, v in data.items() if v is not None}

    doc_ref.set(data)

    return doc_ref


def get_leader(document_id: str) -> Optional[Leader]:
    """
    Get a leader by document ID.

    Args:
        document_id: The document ID (e.g., 'john-doe')

    Returns:
        Leader object if found, None otherwise

    Example:
        >>> leader = get_leader('john-doe')
        >>> leader.name if leader else None
        'John Doe'
    """
    db = get_firestore_client()
    doc_ref = db.collection(COLLECTION_NAME).document(document_id)
    doc = doc_ref.get()

    if not doc.exists:
        return None

    data = doc.to_dict()
    return Leader(
        leader_permalink=data['leader_permalink'],
        name=data['name'],
    )


def leader_exists(document_id: str) -> bool:
    """
    Check if a leader document exists.

    Args:
        document_id: The document ID to check

    Returns:
        True if leader exists, False otherwise

    Example:
        >>> leader_exists('john-doe')
        True
    """
    db = get_firestore_client()
    doc_ref = db.collection(COLLECTION_NAME).document(document_id)
    return doc_ref.get().exists
