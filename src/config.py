"""System configuration management using Firestore."""

import logging
from typing import Optional
from google.cloud import firestore


logger = logging.getLogger(__name__)

# Firestore collection and document for system configuration
CONFIG_COLLECTION = 'system'
CONFIG_DOCUMENT = 'config'

# Default value if config doesn't exist
DEFAULT_PROCESSING_ENABLED = True


_db_client: Optional[firestore.Client] = None


def get_db() -> firestore.Client:
    """Get or create Firestore client."""
    global _db_client
    if _db_client is None:
        _db_client = firestore.Client()
    return _db_client


def is_processing_enabled() -> bool:
    """
    Check if processing is enabled.
    
    Returns:
        True if processing is enabled, False otherwise.
        Defaults to True if config doesn't exist.
    
    Example:
        >>> enabled = is_processing_enabled()
        >>> isinstance(enabled, bool)
        True
    """
    try:
        db = get_db()
        doc_ref = db.collection(CONFIG_COLLECTION).document(CONFIG_DOCUMENT)
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            enabled = data.get('processing_enabled', DEFAULT_PROCESSING_ENABLED)
            logger.info(f"Processing enabled: {enabled}")
            return enabled
        else:
            logger.info(f"Config document doesn't exist, using default: {DEFAULT_PROCESSING_ENABLED}")
            return DEFAULT_PROCESSING_ENABLED
            
    except Exception as e:
        logger.error(f"Error checking processing enabled flag: {e}", exc_info=True)
        # Fail open - allow processing if we can't check the flag
        return DEFAULT_PROCESSING_ENABLED


def set_processing_enabled(enabled: bool) -> None:
    """
    Set the processing enabled flag.
    
    Args:
        enabled: True to enable processing, False to disable.
    
    Example:
        >>> set_processing_enabled(False)
        >>> # Processing is now paused
    """
    try:
        db = get_db()
        doc_ref = db.collection(CONFIG_COLLECTION).document(CONFIG_DOCUMENT)
        
        # Use set with merge to create or update the document
        doc_ref.set({
            'processing_enabled': enabled,
            'updated_at': firestore.SERVER_TIMESTAMP,
        }, merge=True)
        
        logger.info(f"Set processing_enabled to {enabled}")
        
    except Exception as e:
        logger.error(f"Error setting processing enabled flag: {e}", exc_info=True)
        raise
