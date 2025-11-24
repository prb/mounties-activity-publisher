"""Bookkeeping operations for tracking function execution status."""

import logging
from datetime import datetime, timezone
from typing import Optional
from google.cloud import firestore

from .firestore_client import get_firestore_client


logger = logging.getLogger(__name__)

# Firestore collection and document for bookkeeping
BOOKKEEPING_COLLECTION = 'bookkeeping'
BOOKKEEPING_DOCUMENT = 'status'


def update_search_status(status: str, success: bool = False) -> None:
    """
    Update the search function status in bookkeeping.
    
    Args:
        status: Status message ("Green", "Yellow: Backing off.", "Red: {error}")
        success: True if the search completed successfully
    
    Example:
        >>> update_search_status("Green", success=True)
        >>> # Bookkeeping updated
    """
    try:
        db = get_firestore_client()
        doc_ref = db.collection(BOOKKEEPING_COLLECTION).document(BOOKKEEPING_DOCUMENT)
        
        update_data = {
            'search_status': status,
        }
        
        if success:
            update_data['last_search_success'] = firestore.SERVER_TIMESTAMP
        
        doc_ref.set(update_data, merge=True)
        logger.info(f"Updated search bookkeeping: {status}")
        
    except Exception as e:
        logger.error(f"Error updating search bookkeeping: {e}", exc_info=True)
        # Don't raise - bookkeeping failures shouldn't break the function


def update_scrape_status(status: str, success: bool = False) -> None:
    """
    Update the scrape function status in bookkeeping.
    
    Args:
        status: Status message ("Green", "Yellow: Backing off.", "Red: {error}")
        success: True if the scrape completed successfully
    
    Example:
        >>> update_scrape_status("Green", success=True)
        >>> # Bookkeeping updated
    """
    try:
        db = get_firestore_client()
        doc_ref = db.collection(BOOKKEEPING_COLLECTION).document(BOOKKEEPING_DOCUMENT)
        
        update_data = {
            'scrape_status': status,
        }
        
        if success:
            update_data['last_scrape_success'] = firestore.SERVER_TIMESTAMP
        
        doc_ref.set(update_data, merge=True)
        logger.info(f"Updated scrape bookkeeping: {status}")
        
    except Exception as e:
        logger.error(f"Error updating scrape bookkeeping: {e}", exc_info=True)
        # Don't raise - bookkeeping failures shouldn't break the function


def update_publish_status(status: str, success: bool = False) -> None:
    """
    Update the publish function status in bookkeeping.
    
    Args:
        status: Status message ("Green", "Yellow: Backing off.", "Red: {error}")
        success: True if the publish completed successfully (actually published)
    
    Example:
        >>> update_publish_status("Green", success=True)
        >>> # Bookkeeping updated
    """
    try:
        db = get_firestore_client()
        doc_ref = db.collection(BOOKKEEPING_COLLECTION).document(BOOKKEEPING_DOCUMENT)
        
        update_data = {
            'publish_status': status,
        }
        
        # Only update last_publish_success if we actually published
        # (not if we skipped due to existing discord_message_id)
        if success:
            update_data['last_publish_success'] = firestore.SERVER_TIMESTAMP
        
        doc_ref.set(update_data, merge=True)
        logger.info(f"Updated publish bookkeeping: {status}")
        
    except Exception as e:
        logger.error(f"Error updating publish bookkeeping: {e}", exc_info=True)
        # Don't raise - bookkeeping failures shouldn't break the function
