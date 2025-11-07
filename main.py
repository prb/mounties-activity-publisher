"""Cloud Functions entry points for deployment.

This module provides HTTP endpoints for Google Cloud Functions (Gen 2).
Each function is triggered by Cloud Tasks or Cloud Scheduler.
"""

import logging
import functions_framework
from flask import Request

from src.db import initialize_firebase
from src.functions import searcher_handler, scraper_handler, publisher_handler


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Firebase once at module load time
# This will use Application Default Credentials in production
logger.info("Initializing Firebase...")
initialize_firebase(use_emulator=False)
logger.info("Firebase initialized")


@functions_framework.http
def searcher(request: Request):
    """
    Searcher Cloud Function - processes search results and enqueues scraper tasks.

    Triggered by: Cloud Scheduler (initial trigger) or Cloud Tasks (pagination)

    Expected JSON payload:
    {
        "start_index": 0,
        "activity_type": "Backcountry Skiing"
    }

    Returns:
    {
        "status": "success",
        "activities_found": 14,
        "has_next_page": false
    }
    """
    logger.info("=== Searcher function invoked ===")
    request_json = request.get_json(silent=True) or {}
    logger.info(f"Request payload: {request_json}")

    result = searcher_handler(request_json)

    logger.info(f"Searcher result: {result}")
    logger.info("=== Searcher function completed ===")
    return result


@functions_framework.http
def scraper(request: Request):
    """
    Detail Scraper Cloud Function - fetches activity details and stores in Firestore.

    Triggered by: Cloud Tasks (from searcher function)

    Expected JSON payload:
    {
        "activity_url": "https://www.mountaineers.org/activities/activities/..."
    }

    Returns:
    {
        "status": "success",
        "activity_id": "backcountry-ski-..."
    }
    """
    logger.info("=== Scraper function invoked ===")
    request_json = request.get_json(silent=True) or {}
    logger.info(f"Request payload: {request_json}")

    result = scraper_handler(request_json)

    logger.info(f"Scraper result: {result}")
    logger.info("=== Scraper function completed ===")
    return result


@functions_framework.http
def publisher(request: Request):
    """
    Publisher Cloud Function - publishes activities to Discord.

    Triggered by: Cloud Tasks (from scraper function)

    Expected JSON payload:
    {
        "activity_id": "backcountry-ski-..."
    }

    Returns:
    {
        "status": "success",
        "message_id": "1234567890"
    }
    """
    logger.info("=== Publisher function invoked ===")
    request_json = request.get_json(silent=True) or {}
    logger.info(f"Request payload: {request_json}")

    result = publisher_handler(request_json)

    logger.info(f"Publisher result: {result}")
    logger.info("=== Publisher function completed ===")
    return result
