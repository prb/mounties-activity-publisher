# Phase 2: Firestore Operations

This phase implements Firestore database operations for storing activities, leaders, and places.

## Setup

### Install Firebase CLI

```bash
npm install -g firebase-tools
```

### Start Firestore Emulator

```bash
# Start the emulator (runs on localhost:8080 by default)
firebase emulators:start --only firestore
```

Or, set the environment variable and use any port:

```bash
export FIRESTORE_EMULATOR_HOST=localhost:8080
```

## Running Tests

With the emulator running:

```bash
# Run all tests including Firestore tests
uv run pytest tests/

# Run only Firestore tests
uv run pytest tests/test_firestore_operations.py -v
```

## Project Structure

```
src/db/
├── __init__.py              # Public API exports
├── firestore_client.py      # Firebase initialization
├── leaders.py               # Leader CRUD operations
├── places.py                # Place CRUD operations
└── activities.py            # Activity CRUD operations

tests/
└── test_firestore_operations.py  # Comprehensive tests for all operations
```

## Usage Examples

### Initialize Firebase

```python
from src.db import initialize_firebase

# For testing with emulator
initialize_firebase(use_emulator=True)

# For production
initialize_firebase(use_emulator=False)
```

### Create a Leader

```python
from src.models import Leader
from src.db import create_or_update_leader

leader = Leader(
    leader_permalink="https://www.mountaineers.org/members/john-doe",
    name="John Doe"
)
ref = create_or_update_leader(leader)
print(f"Created leader with ID: {ref.id}")
```

### Create a Place

```python
from src.models import Place
from src.db import create_or_update_place

place = Place(
    place_permalink="https://www.mountaineers.org/activities/routes-places/cascades/mount-rainier",
    name="Mount Rainier"
)
ref = create_or_update_place(place)
print(f"Created place with ID: {ref.id}")
```

### Create an Activity

```python
from datetime import datetime
import pytz
from src.models import Activity
from src.db import create_activity, create_or_update_leader, create_or_update_place

# First ensure leader and place exist
create_or_update_leader(leader)
create_or_update_place(place)

# Create activity
activity = Activity(
    activity_permalink="https://www.mountaineers.org/activities/activities/climb-mount-rainier-2026-07-04",
    title="Climb Mount Rainier",
    description="Summit climb via Disappointment Cleaver route",
    difficulty_rating=["Intermediate", "Strenuous"],
    activity_date=datetime(2026, 7, 4, 6, 0, 0, tzinfo=pytz.UTC),
    leader=leader,
    place=place,
)
ref = create_activity(activity)
print(f"Created activity with ID: {ref.id}")
```

### Retrieve an Activity (with Leader and Place)

```python
from src.db import get_activity

activity = get_activity("climb-mount-rainier-2026-07-04")
if activity:
    print(f"Activity: {activity.title}")
    print(f"Leader: {activity.leader.name}")
    print(f"Place: {activity.place.name}")
    print(f"Date: {activity.activity_date}")
```

### Update Discord Message ID

```python
from src.db import update_discord_message_id

update_discord_message_id("climb-mount-rainier-2026-07-04", "1234567890123456")
```

## Collection Schemas

### Leaders Collection

```
leaders/{leader_id}
  - leader_permalink: string
  - name: string
```

Document ID: Final path segment of permalink (e.g., "john-doe")

### Places Collection

```
places/{place_id}
  - place_permalink: string
  - name: string
```

Document ID: Last two path segments joined with underscore (e.g., "cascades_mount-rainier")

### Activities Collection

```
activities/{activity_id}
  - activity_permalink: string
  - title: string
  - description: string
  - difficulty_rating: array<string>
  - activity_date: timestamp
  - leader_ref: reference to leaders/{leader_id}
  - place_ref: reference to places/{place_id}
  - discord_message_id: string (optional)
```

Document ID: Final path segment of permalink (e.g., "climb-mount-rainier-2026-07-04")

## Notes

- The emulator data is ephemeral and cleared when stopped
- Tests automatically clean up after themselves
- All timestamps are stored in UTC
- References are used to link activities to leaders and places
