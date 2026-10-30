"""Cloud Tasks client for enqueueing tasks."""

import os
import json
import logging
from typing import Optional
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2


logger = logging.getLogger(__name__)


# Environment configuration
LOCATION = os.environ.get('GCP_LOCATION', 'us-central1')


def get_project_id() -> str:
    """
    Get the GCP project ID from the GCP_PROJECT environment variable.

    Resolved at call time so that importing this module does not require
    the variable (deployed functions always receive it from Pulumi).

    Raises:
        RuntimeError: If GCP_PROJECT is unset or empty.
    """
    project_id = os.environ.get('GCP_PROJECT', '').strip()
    if not project_id:
        raise RuntimeError(
            "GCP_PROJECT environment variable is not set; "
            "set it to the target Google Cloud project ID."
        )
    return project_id


# Service account for Cloud Tasks OIDC authentication
# Gen2 functions require OIDC tokens for authentication
def get_service_account() -> str:
    """Get the service account email for Cloud Tasks authentication."""
    # Default App Engine service account format
    # For more control, could create a dedicated service account
    return os.environ.get(
        'CLOUD_TASKS_SERVICE_ACCOUNT',
        f'{get_project_id()}@appspot.gserviceaccount.com',
    )


# Queue names
SEARCH_QUEUE = 'search-queue'
SCRAPE_QUEUE = 'scrape-queue'
PUBLISH_QUEUE = 'publish-queue'


# Cloud Function URLs - Gen2 functions have predictable URLs
# Format: https://{region}-{project-id}.cloudfunctions.net/{function-name}
# Can be overridden via environment variables if needed
def get_function_url(function_name: str, env_var: str) -> str:
    """Get a Cloud Function URL, preferring an explicit env var override."""
    override = os.environ.get(env_var)
    if override:
        return override
    return f"https://{LOCATION}-{get_project_id()}.cloudfunctions.net/{function_name}"


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
    parent = client.queue_path(get_project_id(), LOCATION, SEARCH_QUEUE)
    function_url = get_function_url('searcher', 'SEARCH_FUNCTION_URL')

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
            'url': function_url,
            'headers': {
                'Content-Type': 'application/json',
            },
            'body': json.dumps(payload).encode(),
            'oidc_token': {
                'service_account_email': get_service_account(),
                'audience': function_url,
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
    parent = client.queue_path(get_project_id(), LOCATION, SCRAPE_QUEUE)
    function_url = get_function_url('scraper', 'SCRAPE_FUNCTION_URL')

    # Task payload
    payload = {
        'activity_url': activity_url,
    }

    # Construct the task with OIDC authentication
    # Gen2 Cloud Functions require OIDC tokens for authentication
    task = {
        'http_request': {
            'http_method': tasks_v2.HttpMethod.POST,
            'url': function_url,
            'headers': {
                'Content-Type': 'application/json',
            },
            'body': json.dumps(payload).encode(),
            'oidc_token': {
                'service_account_email': get_service_account(),
                'audience': function_url,
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
    parent = client.queue_path(get_project_id(), LOCATION, PUBLISH_QUEUE)
    function_url = get_function_url('publisher', 'PUBLISH_FUNCTION_URL')

    # Task payload
    payload = {
        'activity_id': activity_id,
    }

    # Construct the task with OIDC authentication
    # Gen2 Cloud Functions require OIDC tokens for authentication
    task = {
        'http_request': {
            'http_method': tasks_v2.HttpMethod.POST,
            'url': function_url,
            'headers': {
                'Content-Type': 'application/json',
            },
            'body': json.dumps(payload).encode(),
            'oidc_token': {
                'service_account_email': get_service_account(),
                'audience': function_url,
            },
        }
    }

    # Create the task
    response = client.create_task(request={'parent': parent, 'task': task})

    logger.info(f"Publish task enqueued: {response.name}")

    return response.name
