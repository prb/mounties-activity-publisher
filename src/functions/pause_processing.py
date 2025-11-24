"""Pause Processing Cloud Function - disables searcher and scraper."""

import logging
from typing import Dict, Any

from ..config import set_processing_enabled


logger = logging.getLogger(__name__)


def pause_processing_handler() -> Dict[str, Any]:
    """
    Pause processing by setting the processing_enabled flag to False.
    
    This will cause searcher and scraper to skip processing new tasks.
    
    Returns:
        Dict with status and message.
    
    Example:
        >>> result = pause_processing_handler()
        >>> result['status']
        'success'
    """
    try:
        logger.info("Pausing processing")
        set_processing_enabled(False)
        
        return {
            'status': 'success',
            'message': 'Processing has been paused',
        }
        
    except Exception as e:
        logger.error(f"Error pausing processing: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }
