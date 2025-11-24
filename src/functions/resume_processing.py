"""Resume Processing Cloud Function - enables searcher and scraper."""

import logging
from typing import Dict, Any

from ..config import set_processing_enabled


logger = logging.getLogger(__name__)


def resume_processing_handler() -> Dict[str, Any]:
    """
    Resume processing by setting the processing_enabled flag to True.
    
    This will allow searcher and scraper to process tasks again.
    
    Returns:
        Dict with status and message.
    
    Example:
        >>> result = resume_processing_handler()
        >>> result['status']
        'success'
    """
    try:
        logger.info("Resuming processing")
        set_processing_enabled(True)
        
        return {
            'status': 'success',
            'message': 'Processing has been resumed',
        }
        
    except Exception as e:
        logger.error(f"Error resuming processing: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }
