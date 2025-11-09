"""Cloud Tasks client for enqueueing tasks."""

import os
import json
import logging
from typing import Optional
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2


logger = logging.getLogger(__name__)


# Environment configuration
PROJECT_ID = os.environ.get('GCP_PROJECT', 'your-project-id')
LOCATION = os.environ.get('GCP_LOCATION', 'us-central1')

# Service account for Cloud Tasks OIDC authentication
# Gen2 functions require OIDC tokens for authentication
# This should be the default compute service account
def _get_service_account() -> str:
    """Get the service account email for Cloud Tasks authentication."""
    # Default compute service account format
    # For more control, could create a dedicated service account
    return os.environ.get('CLOUD_TASKS_SERVICE_ACCOUNT', f'{PROJECT_ID}@appspot.gserviceaccount.com')

SERVICE_ACCOUNT = _get_service_account()

# Queue names
SEARCH_QUEUE = 'search-queue'
SCRAPE_QUEUE = 'scrape-queue'
PUBLISH_QUEUE = 'publish-queue'

# Cloud Function URLs - Gen2 functions have predictable URLs
# Format: https://{region}-{project-id}.cloudfunctions.net/{function-name}
# Can be overridden via environment variables if needed
def _construct_function_url(function_name: str) -> str:
    """Construct Cloud Function Gen2 URL based on naming convention."""
    return f"https://{LOCATION}-{PROJECT_ID}.cloudfunctions.net/{function_name}"

SEARCH_FUNCTION_URL = os.environ.get('SEARCH_FUNCTION_URL', _construct_function_url('searcher'))
SCRAPE_FUNCTION_URL = os.environ.get('SCRAPE_FUNCTION_URL', _construct_function_url('scraper'))
PUBLISH_FUNCTION_URL = os.environ.get('PUBLISH_FUNCTION_URL', _construct_function_url('publisher'))


_tasks_client: Optional[tasks_v2.CloudTasksClient] = None


def get_tasks_client() -> tasks_v2.CloudTasksClient:
    """Get or create Cloud Tasks client."""
    global _tasks_client
    if _tasks_client is None:
        _tasks_client = tasks_v2.CloudTasksClient()
    return _tasks_client


def enqueue_search_task(start_index: int, activity_type: str = 'Backcountry Skiing') -> str:
    """
    Enqueue a search task to fetch and process search results.

    Args:
        start_index: The starting index for pagination
        activity_type: The type of activity to search for

    Returns:
        The task name

    Example:
        >>> task_name = enqueue_search_task(0)
        >>> 'search-queue' in task_name
        True
    """
    logger.info(f"Enqueueing search task: start_index={start_index}, activity_type={activity_type}")

    client = get_tasks_client()

    # Construct the queue path
    parent = client.queue_path(PROJECT_ID, LOCATION, SEARCH_QUEUE)

    # Task payload
    payload = {
        'start_index': start_index,
        'activity_type': activity_type,
    }

    # Construct the task with OIDC authentication
    # Gen2 Cloud Functions require OIDC tokens for authentication
    task = {
        'http_request': {
            'http_method': tasks_v2.HttpMethod.POST,
            'url': SEARCH_FUNCTION_URL,
            'headers': {
                'Content-Type': 'application/json',
            },
            'body': json.dumps(payload).encode(),
            'oidc_token': {
                'service_account_email': SERVICE_ACCOUNT,
                'audience': SEARCH_FUNCTION_URL,
            },
        }
    }

    # Create the task
    response = client.create_task(request={'parent': parent, 'task': task})

    logger.info(f"Search task enqueued: {response.name}")

    return response.name


def enqueue_scrape_task(activity_url: str) -> str:
    """
    Enqueue a scrape task to fetch and process an activity detail page.

    Args:
        activity_url: The URL of the activity detail page

    Returns:
        The task name

    Example:
        >>> task_name = enqueue_scrape_task('https://www.mountaineers.org/activities/activities/some-activity')
        >>> 'scrape-queue' in task_name
        True
    """
    logger.info(f"Enqueueing scrape task: {activity_url}")

    client = get_tasks_client()

    # Construct the queue path
    parent = client.queue_path(PROJECT_ID, LOCATION, SCRAPE_QUEUE)

    # Task payload
    payload = {
        'activity_url': activity_url,
    }

    # Construct the task with OIDC authentication
    # Gen2 Cloud Functions require OIDC tokens for authentication
    task = {
        'http_request': {
            'http_method': tasks_v2.HttpMethod.POST,
            'url': SCRAPE_FUNCTION_URL,
            'headers': {
                'Content-Type': 'application/json',
            },
            'body': json.dumps(payload).encode(),
            'oidc_token': {
                'service_account_email': SERVICE_ACCOUNT,
                'audience': SCRAPE_FUNCTION_URL,
            },
        }
    }

    # Create the task
    response = client.create_task(request={'parent': parent, 'task': task})

    logger.debug(f"Scrape task enqueued: {response.name}")

    return response.name


def enqueue_publish_task(activity_id: str) -> str:
    """
    Enqueue a publish task to send an activity to Discord.

    Args:
        activity_id: The Firestore document ID of the activity

    Returns:
        The task name

    Example:
        >>> task_name = enqueue_publish_task('backcountry-ski-snoqualmie-2026-02-10')
        >>> 'publish-queue' in task_name
        True
    """
    logger.info(f"Enqueueing publish task: {activity_id}")

    client = get_tasks_client()

    # Construct the queue path
    parent = client.queue_path(PROJECT_ID, LOCATION, PUBLISH_QUEUE)

    # Task payload
    payload = {
        'activity_id': activity_id,
    }

    # Construct the task with OIDC authentication
    # Gen2 Cloud Functions require OIDC tokens for authentication
    task = {
        'http_request': {
            'http_method': tasks_v2.HttpMethod.POST,
            'url': PUBLISH_FUNCTION_URL,
            'headers': {
                'Content-Type': 'application/json',
            },
            'body': json.dumps(payload).encode(),
            'oidc_token': {
                'service_account_email': SERVICE_ACCOUNT,
                'audience': PUBLISH_FUNCTION_URL,
            },
        }
    }

    # Create the task
    response = client.create_task(request={'parent': parent, 'task': task})

    logger.info(f"Publish task enqueued: {response.name}")

    return response.name
