"""Bookkeeping collection operations."""

from datetime import datetime
from typing import Optional

from ..models import BookkeepingStatus
from .firestore_client import get_firestore_client


COLLECTION_NAME = 'bookkeeping'
DOCUMENT_ID = 'status'


def update_search_status(status: str, success_time: Optional[datetime] = None) -> None:
    """
    Update search function status in bookkeeping.

    Args:
        status: Status message (e.g., "Green", "Yellow: Backing off.", "Red: {message}")
        success_time: Optional timestamp to record as last_search_success (only on successful completion)

    Example:
        >>> from datetime import datetime
        >>> update_search_status("Green", datetime.utcnow())
        >>> update_search_status("Red: Connection timeout")
    """
    db = get_firestore_client()
    doc_ref = db.collection(COLLECTION_NAME).document(DOCUMENT_ID)

    update_data = {'search_status': status}
    if success_time is not None:
        update_data['last_search_success'] = success_time

    doc_ref.set(update_data, merge=True)


def update_scrape_status(status: str, success_time: Optional[datetime] = None) -> None:
    """
    Update scrape function status in bookkeeping.

    Args:
        status: Status message (e.g., "Green", "Yellow: Backing off.", "Red: {message}")
        success_time: Optional timestamp to record as last_scrape_success (only on successful completion)

    Example:
        >>> from datetime import datetime
        >>> update_scrape_status("Green", datetime.utcnow())
        >>> update_scrape_status("Red: Parse error")
    """
    db = get_firestore_client()
    doc_ref = db.collection(COLLECTION_NAME).document(DOCUMENT_ID)

    update_data = {'scrape_status': status}
    if success_time is not None:
        update_data['last_scrape_success'] = success_time

    doc_ref.set(update_data, merge=True)


def update_publish_status(status: str, success_time: Optional[datetime] = None) -> None:
    """
    Update publish function status in bookkeeping.

    Args:
        status: Status message (e.g., "Green", "Yellow: Backing off.", "Red: {message}")
        success_time: Optional timestamp to record as last_publish_success (only on successful publication,
                     not when skipped due to existing discord_message_id)

    Example:
        >>> from datetime import datetime
        >>> update_publish_status("Green", datetime.utcnow())
        >>> update_publish_status("Yellow: Backing off.")
    """
    db = get_firestore_client()
    doc_ref = db.collection(COLLECTION_NAME).document(DOCUMENT_ID)

    update_data = {'publish_status': status}
    if success_time is not None:
        update_data['last_publish_success'] = success_time

    doc_ref.set(update_data, merge=True)


def get_bookkeeping_status() -> BookkeepingStatus:
    """
    Get current bookkeeping status.

    Returns:
        BookkeepingStatus object with all status fields

    Example:
        >>> status = get_bookkeeping_status()
        >>> status.search_status
        'Green'
    """
    db = get_firestore_client()
    doc_ref = db.collection(COLLECTION_NAME).document(DOCUMENT_ID)
    doc = doc_ref.get()

    if not doc.exists:
        return BookkeepingStatus()

    data = doc.to_dict()

    return BookkeepingStatus(
        last_search_success=data.get('last_search_success'),
        search_status=data.get('search_status'),
        last_scrape_success=data.get('last_scrape_success'),
        scrape_status=data.get('scrape_status'),
        last_publish_success=data.get('last_publish_success'),
        publish_status=data.get('publish_status'),
    )
