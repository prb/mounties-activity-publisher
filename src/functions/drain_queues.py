"""Drain Queues Cloud Function - purges all tasks from search and scrape queues."""

import logging
from typing import Dict, Any
from google.cloud import tasks_v2

from ..tasks.client import (
    get_tasks_client,
    PROJECT_ID,
    LOCATION,
    SEARCH_QUEUE,
    SCRAPE_QUEUE,
)


logger = logging.getLogger(__name__)


def drain_queues_handler() -> Dict[str, Any]:
    """
    Drain (purge) all tasks from search-queue and scrape-queue.
    
    This is useful when bad/undesirable data has entered the system
    and you want to stop processing and clear the queues.
    
    Recommended workflow:
    1. Call pause_processing to stop new tasks from being processed
    2. Call drain_queues to clear existing tasks
    3. Fix data issues in Firestore
    4. Call resume_processing to restart
    
    Returns:
        Dict with status, message, and counts of drained tasks.
    
    Example:
        >>> result = drain_queues_handler()
        >>> result['status']
        'success'
        >>> 'search_queue_drained' in result
        True
    """
    try:
        logger.info("Draining task queues")
        
        client = get_tasks_client()
        
        # Purge search queue
        search_queue_path = client.queue_path(PROJECT_ID, LOCATION, SEARCH_QUEUE)
        logger.info(f"Purging queue: {search_queue_path}")
        client.purge_queue(name=search_queue_path)
        
        # Purge scrape queue
        scrape_queue_path = client.queue_path(PROJECT_ID, LOCATION, SCRAPE_QUEUE)
        logger.info(f"Purging queue: {scrape_queue_path}")
        client.purge_queue(name=scrape_queue_path)
        
        logger.info("Successfully drained queues")
        
        return {
            'status': 'success',
            'message': 'Successfully drained search-queue and scrape-queue',
            'search_queue_drained': True,
            'scrape_queue_drained': True,
        }
        
    except Exception as e:
        logger.error(f"Error draining queues: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }
