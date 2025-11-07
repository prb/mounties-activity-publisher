## Phase 3: Searcher & Detail Scraper Functions

This phase implements the core Cloud Functions that tie together parsing (Phase 1) and Firestore operations (Phase 2) with HTTP fetching and Cloud Tasks enqueueing.

## Overview

**Data Flow:**
```
Scheduled Trigger
    ↓
[Searcher Function] ←─┐
    ↓                  │ (pagination)
    ├─→ enqueue scrape tasks (one per activity)
    └─→ enqueue next search task (if more pages)
            ↓
[Detail Scraper Function]
    ↓
    ├─→ fetch activity detail page
    ├─→ create/update leader in Firestore
    ├─→ create/update place in Firestore
    ├─→ create activity in Firestore
    └─→ enqueue publish task
            ↓
[Publisher Function] (Phase 4)
```

## Project Structure

```
src/
├── http_client.py           # HTTP client with User-Agent
├── tasks/
│   ├── __init__.py
│   └── client.py            # Cloud Tasks enqueueing
└── functions/
    ├── __init__.py
    ├── searcher.py          # Searcher Cloud Function
    └── scraper.py           # Detail Scraper Cloud Function

tests/
└── test_functions.py        # Tests for both functions (10 tests)
```

## Components

### 1. HTTP Client (`src/http_client.py`)

Provides HTTP fetching with proper User-Agent header:

```python
from src.http_client import fetch_page, fetch_search_results

# Fetch any page
html = fetch_page('https://www.mountaineers.org/activities/activities/some-activity')

# Fetch search results with pagination
html = fetch_search_results(start_index=0, activity_type='Backcountry Skiing')
```

**Features:**
- User-Agent: `mounties-activities-discord-publisher/{version}`
- Version from `APP_VERSION` env var (or "dev")
- Configurable timeout (default 30s)
- Raises exceptions on HTTP errors

### 2. Cloud Tasks Client (`src/tasks/client.py`)

Enqueues tasks to three queues:

```python
from src.tasks import enqueue_search_task, enqueue_scrape_task, enqueue_publish_task

# Enqueue a search task
task_name = enqueue_search_task(start_index=0, activity_type='Backcountry Skiing')

# Enqueue a scrape task
task_name = enqueue_scrape_task(activity_url='https://...')

# Enqueue a publish task
task_name = enqueue_publish_task(activity_id='backcountry-ski-2026-02-10')
```

**Configuration (via environment variables):**
- `GCP_PROJECT`: Your Google Cloud project ID
- `GCP_LOCATION`: Region (default: us-central1)
- `SEARCH_FUNCTION_URL`: URL of searcher function
- `SCRAPE_FUNCTION_URL`: URL of scraper function
- `PUBLISH_FUNCTION_URL`: URL of publisher function

### 3. Searcher Function (`src/functions/searcher.py`)

Entry point for Cloud Functions - processes search results.

**Input (JSON):**
```json
{
  "start_index": 0,
  "activity_type": "Backcountry Skiing"
}
```

**Output (JSON):**
```json
{
  "status": "success",
  "activities_found": 14,
  "has_next_page": false
}
```

**Process:**
1. Fetches search results from Mountaineers website
2. Extracts activity detail URLs
3. Enqueues a scraper task for each URL
4. If there's a next page, enqueues another search task

**Error Handling:**
- Continues processing if individual scrape task enqueueing fails
- Returns error status if HTTP fetch or parsing fails

### 4. Detail Scraper Function (`src/functions/scraper.py`)

Entry point for Cloud Functions - processes activity detail pages.

**Input (JSON):**
```json
{
  "activity_url": "https://www.mountaineers.org/activities/activities/backcountry-ski-2026-02-10"
}
```

**Output (JSON):**
```json
{
  "status": "success",
  "activity_id": "backcountry-ski-2026-02-10"
}
```

Or if skipped:
```json
{
  "status": "skipped",
  "activity_id": "backcountry-ski-2026-02-10",
  "reason": "Activity already exists in Firestore"
}
```

**Process:**
1. Checks if activity already exists (skips if so)
2. Fetches activity detail page
3. Parses all fields (title, description, date, leader, place, etc.)
4. Creates/updates leader document
5. Creates/updates place document
6. Creates activity document
7. Enqueues publish task

**Error Handling:**
- Skips activities that already exist
- Returns error if HTTP fetch or parsing fails
- Continues if publish task enqueueing fails (activity already saved)

## Testing

All tests use mocking to avoid real HTTP requests and Cloud Tasks calls.

```bash
# Run all Phase 3 tests
uv run pytest tests/test_functions.py -v

# Run all tests (Phases 1 & 3)
uv run pytest tests/test_search_parser.py tests/test_detail_parser.py tests/test_functions.py -v
```

**Test Coverage:**
- Searcher: 5 tests (success, pagination, custom type, errors, partial failures)
- Scraper: 5 tests (success, skip existing, errors, missing params, partial failures)

## Usage Examples

### Searcher Function

```python
from src.functions import searcher_handler

# Process first page of search results
result = searcher_handler({
    'start_index': 0,
    'activity_type': 'Backcountry Skiing'
})

print(f"Status: {result['status']}")
print(f"Found {result['activities_found']} activities")
print(f"Has next page: {result['has_next_page']}")
```

### Scraper Function

```python
from src.functions import scraper_handler
from src.db import initialize_firebase

# Initialize Firestore (required)
initialize_firebase(use_emulator=True)

# Scrape an activity
result = scraper_handler({
    'activity_url': 'https://www.mountaineers.org/activities/activities/backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10'
})

print(f"Status: {result['status']}")
if result['status'] == 'success':
    print(f"Created activity: {result['activity_id']}")
elif result['status'] == 'skipped':
    print(f"Skipped: {result['reason']}")
```

## Integration with Cloud Functions

These handlers are designed to be deployed as Cloud Functions (Gen 2):

```python
# functions.py (for deployment)
import functions_framework
from src.db import initialize_firebase
from src.functions import searcher_handler, scraper_handler

# Initialize Firebase once at module load
initialize_firebase()

@functions_framework.http
def searcher(request):
    """Searcher Cloud Function entry point."""
    request_json = request.get_json(silent=True)
    result = searcher_handler(request_json or {})
    return result

@functions_framework.http
def scraper(request):
    """Scraper Cloud Function entry point."""
    request_json = request.get_json(silent=True)
    result = scraper_handler(request_json or {})
    return result
```

## Environment Variables

Required for production deployment:

```bash
# Google Cloud
export GCP_PROJECT=your-project-id
export GCP_LOCATION=us-central1

# Cloud Function URLs (set after deployment)
export SEARCH_FUNCTION_URL=https://us-central1-project.cloudfunctions.net/searcher
export SCRAPE_FUNCTION_URL=https://us-central1-project.cloudfunctions.net/scraper
export PUBLISH_FUNCTION_URL=https://us-central1-project.cloudfunctions.net/publisher

# Application version (set to Git SHA in CI/CD)
export APP_VERSION=abc123def

# For local testing with emulator
export FIRESTORE_EMULATOR_HOST=localhost:8080
```

## Notes

- HTTP requests have 30-second timeout (configurable)
- User-Agent includes version for tracking
- Searcher processes one page at a time (enqueues next page)
- Scraper is idempotent (skips existing activities)
- All errors are logged and returned in response
- Partial failures are handled gracefully (continues processing)

## Next Steps

Phase 4 will implement:
- Discord Publisher function
- Discord message formatting
- Discord API integration
- Update of `discord_message_id` field
